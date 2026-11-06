from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import TEACHER_CLASS_ROLES, require_class_teacher
from app.database import get_db
from app.dependencies import require_role
from app.grading_batches import finish_batch_item
from app.models import (
    Assignment,
    ClassMember,
    GradingBatch,
    GradingBatchItem,
    Submission,
    User,
)
from app.submission_events import publish_batch_status
from app.worker import enqueue_grade_submission


router = APIRouter(prefix="/api/grading-batches", tags=["grading-batches"])


class CreateGradingBatchRequest(BaseModel):
    assignment_id: int


def _timestamp(value):
    return value.isoformat() if value else None


def _batch_payload(
    batch: GradingBatch,
    items: list[GradingBatchItem] | None = None,
) -> dict:
    finished = batch.completed_submissions + batch.failed_submissions
    payload = {
        "id": batch.id,
        "assignment_id": batch.assignment_id,
        "teacher_id": batch.teacher_id,
        "total_submissions": batch.total_submissions,
        "completed_submissions": batch.completed_submissions,
        "failed_submissions": batch.failed_submissions,
        "finished_submissions": finished,
        "progress_percent": round(finished * 100 / batch.total_submissions, 1)
        if batch.total_submissions
        else 100.0,
        "status": batch.status,
        "error_message": batch.error_message,
        "created_at": _timestamp(batch.created_at),
        "completed_at": _timestamp(batch.completed_at),
    }
    if items is not None:
        counts = Counter(item.status for item in items)
        payload["queued_submissions"] = counts["queued"]
        payload["grading_submissions"] = counts["grading"]
        payload["items"] = [
            {
                "id": item.id,
                "submission_id": item.submission_id,
                "task_id": item.task_id,
                "status": item.status,
                "error_message": item.error_message,
                "created_at": _timestamp(item.created_at),
                "started_at": _timestamp(item.started_at),
                "completed_at": _timestamp(item.completed_at),
            }
            for item in items
        ]
    return payload


async def _require_batch_access(
    db: AsyncSession,
    teacher_id: int,
    batch_id: int,
) -> GradingBatch:
    batch = (
        await db.execute(select(GradingBatch).where(GradingBatch.id == batch_id))
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批改批次不存在")
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == batch.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    await require_class_teacher(db, teacher_id, assignment.class_id)
    return batch


@router.post("", status_code=202)
async def create_grading_batch(
    body: CreateGradingBatchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == body.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    await require_class_teacher(db, user.id, assignment.class_id)

    active_batch = (
        await db.execute(
            select(GradingBatch).where(
                GradingBatch.assignment_id == body.assignment_id,
                GradingBatch.status.in_(("pending", "grading")),
            )
        )
    ).scalar_one_or_none()
    if active_batch:
        raise HTTPException(status_code=409, detail="该作业已有进行中的批改批次")

    submissions = (
        await db.execute(
            select(Submission)
            .where(
                Submission.assignment_id == body.assignment_id,
                Submission.status == "pending",
            )
            .order_by(Submission.id)
        )
    ).scalars().all()
    if not submissions:
        raise HTTPException(status_code=409, detail="该作业没有待批改提交")

    batch = GradingBatch(
        assignment_id=body.assignment_id,
        teacher_id=user.id,
        total_submissions=len(submissions),
        completed_submissions=0,
        failed_submissions=0,
        status="grading",
    )
    db.add(batch)
    await db.flush()

    items = []
    for submission in submissions:
        submission.status = "grading"
        item = GradingBatchItem(
            batch_id=batch.id,
            submission_id=submission.id,
            status="queued",
        )
        db.add(item)
        items.append(item)
    await db.commit()

    for submission, item in zip(submissions, items, strict=True):
        try:
            item.task_id = enqueue_grade_submission(submission.id, batch.id)
            await db.commit()
        except Exception as exc:
            submission.status = "pending"
            await db.commit()
            failed_batch = await finish_batch_item(
                db,
                batch.id,
                submission.id,
                "failed",
                exc,
            )
            await publish_batch_status(
                failed_batch.id,
                failed_batch.status,
                failed_batch.total_submissions,
                failed_batch.completed_submissions,
                failed_batch.failed_submissions,
            )

    await db.refresh(batch)
    for item in items:
        await db.refresh(item)
    await publish_batch_status(
        batch.id,
        batch.status,
        batch.total_submissions,
        batch.completed_submissions,
        batch.failed_submissions,
    )
    return _batch_payload(batch, items)


@router.get("")
async def list_grading_batches(
    assignment_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    managed_classes = select(ClassMember.class_id).where(
        ClassMember.user_id == user.id,
        ClassMember.role.in_(TEACHER_CLASS_ROLES),
    )
    query = (
        select(GradingBatch)
        .join(Assignment, Assignment.id == GradingBatch.assignment_id)
        .where(Assignment.class_id.in_(managed_classes))
    )
    if assignment_id is not None:
        query = query.where(GradingBatch.assignment_id == assignment_id)
    batches = (
        await db.execute(query.order_by(GradingBatch.created_at.desc()).limit(limit))
    ).scalars().all()
    return [_batch_payload(batch) for batch in batches]


@router.get("/{batch_id}")
async def get_grading_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    batch = await _require_batch_access(db, user.id, batch_id)
    items = (
        await db.execute(
            select(GradingBatchItem)
            .where(GradingBatchItem.batch_id == batch_id)
            .order_by(GradingBatchItem.id)
        )
    ).scalars().all()
    return _batch_payload(batch, items)
