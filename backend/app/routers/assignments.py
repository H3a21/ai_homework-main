from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import require_assignment_access, require_class_teacher
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Assignment, Class, ClassMember, Question, Subject, User

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


class CreateAssignmentRequest(BaseModel):
    title: str
    class_id: int
    subject_id: int
    due_date: Optional[str] = None
    questions: list = []


class QuestionItem(BaseModel):
    question_number: int
    content: str = ""
    answer: str = ""
    max_score: float = 0
    knowledge_point_id: Optional[int] = None
    difficulty: float = 0.0
    discrimination: float = 1.0


@router.get("")
async def list_assignments(
    class_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Assignment)
    if user.role == "teacher":
        query = query.where(Assignment.teacher_id == user.id)
    else:
        result = await db.execute(
            select(ClassMember.class_id).where(
                ClassMember.user_id == user.id, ClassMember.role == "student"
            )
        )
        class_ids = [r[0] for r in result]
        query = query.where(Assignment.class_id.in_(class_ids))
    if class_id:
        query = query.where(Assignment.class_id == class_id)
    query = query.order_by(Assignment.created_at.desc())

    result = await db.execute(query)
    assignments = result.scalars().all()

    data = []
    for a in assignments:
        cls_result = await db.execute(select(Class).where(Class.id == a.class_id))
        cls = cls_result.scalar_one_or_none()
        subj_result = await db.execute(select(Subject).where(Subject.id == a.subject_id))
        subj = subj_result.scalar_one_or_none()
        q_result = await db.execute(
            select(Question).where(Question.assignment_id == a.id)
        )
        questions = q_result.scalars().all()
        data.append({
            "id": a.id,
            "title": a.title,
            "class_id": a.class_id,
            "class_name": cls.name if cls else "",
            "subject_id": a.subject_id,
            "subject_name": subj.name if subj else "",
            "teacher_id": a.teacher_id,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "question_count": len(questions),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return data


@router.get("/{assignment_id}")
async def get_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="作业不存在")

    await require_assignment_access(db, user, a)

    cls_result = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_result.scalar_one_or_none()
    subj_result = await db.execute(select(Subject).where(Subject.id == a.subject_id))
    subj = subj_result.scalar_one_or_none()
    q_result = await db.execute(
        select(Question).where(Question.assignment_id == a.id).order_by(Question.question_number)
    )
    questions = q_result.scalars().all()

    question_items = []
    for q in questions:
        item = {
            "id": q.id,
            "question_number": q.question_number,
            "content": q.content,
            "max_score": float(q.max_score),
            "knowledge_point_id": q.knowledge_point_id,
            "difficulty": float(q.difficulty),
            "discrimination": float(q.discrimination),
        }
        if user.role == "teacher":
            item["answer"] = q.answer
        question_items.append(item)

    return {
        "id": a.id,
        "title": a.title,
        "class_id": a.class_id,
        "class_name": cls.name if cls else "",
        "subject_id": a.subject_id,
        "subject_name": subj.name if subj else "",
        "teacher_id": a.teacher_id,
        "due_date": a.due_date.isoformat() if a.due_date else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "questions": question_items,
    }


@router.post("")
async def create_assignment(
    body: CreateAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    cls = (
        await db.execute(select(Class).where(Class.id == body.class_id))
    ).scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    await require_class_teacher(db, user.id, body.class_id)

    subject = (
        await db.execute(select(Subject).where(Subject.id == body.subject_id))
    ).scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    assignment = Assignment(
        title=body.title,
        class_id=body.class_id,
        subject_id=body.subject_id,
        teacher_id=user.id,
        due_date=body.due_date,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    for i, q in enumerate(body.questions):
        question = Question(
            assignment_id=assignment.id,
            question_number=q.get("question_number", i + 1),
            content=q.get("content", ""),
            answer=q.get("answer", ""),
            max_score=q.get("max_score", 0),
            knowledge_point_id=q.get("knowledge_point_id"),
            difficulty=max(-3.0, min(3.0, float(q.get("difficulty", 0.0)))),
            discrimination=max(
                0.1, min(3.0, float(q.get("discrimination", 1.0)))
            ),
        )
        db.add(question)
    await db.commit()

    return {"id": assignment.id, "title": assignment.title, "message": "创建成功"}
