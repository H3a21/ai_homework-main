from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import (
    TEACHER_CLASS_ROLES,
    require_assignment_access,
    require_submission_access,
)
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.image_uploads import validate_image_upload, validate_owned_image_paths
from app.models import (
    Assignment,
    ClassMember,
    GradingResult,
    Question,
    Submission,
    SubmissionImage,
    User,
)
from app.object_storage import object_exists, read_object, store_submission_image
from app.worker import enqueue_grade_submission

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


class CreateSubmissionRequest(BaseModel):
    assignment_id: int
    image_paths: list[str] = Field(default_factory=list)
    auto_grade: bool = True


@router.get("")
async def list_submissions(
    assignment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Submission)
    if user.role == "student":
        query = query.where(Submission.student_id == user.id)
    elif user.role == "teacher":
        query = (
            query.join(Assignment, Assignment.id == Submission.assignment_id)
            .join(ClassMember, ClassMember.class_id == Assignment.class_id)
            .where(
                ClassMember.user_id == user.id,
                ClassMember.role.in_(TEACHER_CLASS_ROLES),
            )
        )
        if student_id:
            query = query.where(Submission.student_id == student_id)
    else:
        raise HTTPException(status_code=403, detail="权限不足")
    if assignment_id:
        query = query.where(Submission.assignment_id == assignment_id)
    query = query.order_by(Submission.submitted_at.desc())

    result = await db.execute(query)
    submissions = result.scalars().all()

    data = []
    for s in submissions:
        a_result = await db.execute(select(Assignment).where(Assignment.id == s.assignment_id))
        a = a_result.scalar_one_or_none()
        u_result = await db.execute(select(User).where(User.id == s.student_id))
        u = u_result.scalar_one_or_none()
        img_result = await db.execute(
            select(SubmissionImage).where(SubmissionImage.submission_id == s.id)
        )
        images = img_result.scalars().all()
        gr_result = await db.execute(
            select(GradingResult).where(GradingResult.submission_id == s.id)
        )
        results = gr_result.scalars().all()
        data.append({
            "id": s.id,
            "assignment_id": s.assignment_id,
            "assignment_title": a.title if a else "",
            "student_id": s.student_id,
            "student_name": u.display_name if u else "",
            "status": s.status,
            "total_score": float(s.total_score) if s.total_score else None,
            "comment": s.comment,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            "graded_at": s.graded_at.isoformat() if s.graded_at else None,
            "image_count": len(images),
            "graded_count": len(results),
        })
    return data


@router.post("/images", status_code=201)
async def upload_submission_image(
    image: UploadFile = File(...),
    user: User = Depends(require_role("student")),
):
    content = await image.read(settings.MAX_UPLOAD_IMAGE_BYTES + 1)
    suffix, content_type = validate_image_upload(
        image.filename or "",
        image.content_type,
        content,
    )
    try:
        image_path = await store_submission_image(
            user.id,
            content,
            suffix,
            content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="图片存储服务暂不可用") from exc
    return {
        "image_path": image_path,
        "filename": image.filename,
        "content_type": content_type,
        "size": len(content),
    }


@router.get("/{submission_id}")
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="提交记录不存在")

    a_result = await db.execute(select(Assignment).where(Assignment.id == s.assignment_id))
    a = a_result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="作业不存在")
    await require_submission_access(db, user, s, a)

    u_result = await db.execute(select(User).where(User.id == s.student_id))
    u = u_result.scalar_one_or_none()

    img_result = await db.execute(
        select(SubmissionImage).where(SubmissionImage.submission_id == s.id).order_by(SubmissionImage.page_number)
    )
    images = img_result.scalars().all()

    q_result = await db.execute(
        select(Question).where(Question.assignment_id == s.assignment_id).order_by(Question.question_number)
    )
    questions = q_result.scalars().all()

    gr_result = await db.execute(
        select(GradingResult).where(GradingResult.submission_id == s.id)
    )
    results = gr_result.scalars().all()
    results_map = {r.question_id: r for r in results}

    return {
        "id": s.id,
        "assignment_id": s.assignment_id,
        "assignment_title": a.title if a else "",
        "student_id": s.student_id,
        "student_name": u.display_name if u else "",
        "status": s.status,
        "total_score": float(s.total_score) if s.total_score else None,
        "comment": s.comment,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        "graded_at": s.graded_at.isoformat() if s.graded_at else None,
        "images": [
            {
                "id": img.id,
                "image_path": f"/api/submissions/{s.id}/images/{img.id}",
                "page_number": img.page_number,
            }
            for img in images
        ],
        "questions": [
            {
                "id": q.id,
                "question_number": q.question_number,
                "content": q.content,
                "max_score": float(q.max_score),
                "score": float(results_map[q.id].score) if q.id in results_map else None,
                "feedback": results_map[q.id].feedback if q.id in results_map else None,
            }
            for q in questions
        ],
    }


@router.get("/{submission_id}/images/{image_id}")
async def get_submission_image(
    submission_id: int,
    image_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    submission = (
        await db.execute(select(Submission).where(Submission.id == submission_id))
    ).scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")

    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == submission.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    await require_submission_access(db, user, submission, assignment)

    image_record = (
        await db.execute(
            select(SubmissionImage).where(
                SubmissionImage.id == image_id,
                SubmissionImage.submission_id == submission_id,
            )
        )
    ).scalar_one_or_none()
    if not image_record:
        raise HTTPException(status_code=404, detail="图片不存在")

    try:
        stored = await read_object(image_record.image_path)
    except Exception as exc:
        if getattr(exc, "code", "") in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="图片不存在") from exc
        raise HTTPException(status_code=503, detail="图片存储服务暂不可用") from exc
    return Response(content=stored.content, media_type=stored.content_type)


@router.post("", status_code=202)
async def create_submission(
    body: CreateSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Assignment).where(Assignment.id == body.assignment_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="作业不存在")

    await require_assignment_access(db, user, a)

    validate_owned_image_paths(user.id, body.image_paths)
    try:
        paths_exist = [await object_exists(path) for path in body.image_paths]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="图片存储服务暂不可用") from exc
    if not all(paths_exist):
        raise HTTPException(status_code=400, detail="提交中包含不存在的图片")

    existing = await db.execute(
        select(Submission).where(
            Submission.assignment_id == body.assignment_id,
            Submission.student_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="已提交过该作业")

    submission = Submission(
        assignment_id=body.assignment_id,
        student_id=user.id,
        status="pending",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    for i, path in enumerate(body.image_paths):
        img = SubmissionImage(
            submission_id=submission.id,
            image_path=path,
            page_number=i + 1,
        )
        db.add(img)
    await db.commit()

    task_id = None
    if body.auto_grade:
        submission.status = "grading"
        await db.commit()
        try:
            task_id = enqueue_grade_submission(submission.id)
        except Exception:
            submission.status = "pending"
            await db.commit()
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "提交已保存，但批改任务暂时无法进入队列",
                    "submission_id": submission.id,
                },
            )

    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "status": submission.status,
        "task_id": task_id,
        "message": "提交成功，批改任务已进入队列" if task_id else "提交成功",
    }


@router.post("/{submission_id}/grade", status_code=202)
async def trigger_grade(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == submission.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    await require_submission_access(db, user, submission, assignment)

    if submission.status == "completed":
        raise HTTPException(status_code=409, detail="该提交已完成批改")
    if submission.status == "grading":
        raise HTTPException(status_code=409, detail="该提交已在批改队列中")

    submission.status = "grading"
    await db.commit()
    try:
        task_id = enqueue_grade_submission(submission_id)
    except Exception:
        submission.status = "pending"
        await db.commit()
        raise HTTPException(status_code=503, detail="批改任务暂时无法进入队列")

    return {
        "message": "批改任务已进入队列",
        "submission_id": submission_id,
        "task_id": task_id,
    }
