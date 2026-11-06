from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import require_submission_access
from app.database import get_db
from app.dependencies import require_role
from app.models import Assignment, AuditLog, GradingAttempt, Submission, User


router = APIRouter(prefix="/api/history", tags=["history"])


async def _require_managed_submission(
    db: AsyncSession,
    user: User,
    submission_id: int,
) -> Submission:
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
    return submission


@router.get("/submissions/{submission_id}/attempts")
async def list_grading_attempts(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    await _require_managed_submission(db, user, submission_id)
    attempts = (
        await db.execute(
            select(GradingAttempt)
            .where(GradingAttempt.submission_id == submission_id)
            .order_by(GradingAttempt.attempt_number.desc())
        )
    ).scalars().all()
    return [
        {
            "id": attempt.id,
            "submission_id": attempt.submission_id,
            "attempt_number": attempt.attempt_number,
            "status": attempt.status,
            "total_score": float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            "raw_ocr_result": attempt.raw_ocr_result,
            "result_snapshot": attempt.result_snapshot,
            "grader_version": attempt.grader_version,
            "error_message": attempt.error_message,
            "duration_ms": attempt.duration_ms,
            "started_at": attempt.started_at.isoformat()
            if attempt.started_at
            else None,
            "completed_at": attempt.completed_at.isoformat()
            if attempt.completed_at
            else None,
        }
        for attempt in attempts
    ]


@router.get("/submissions/{submission_id}/audit")
async def list_submission_audit(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    await _require_managed_submission(db, user, submission_id)
    records = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == "submission",
                AuditLog.resource_id == submission_id,
            )
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        )
    ).scalars().all()
    return [
        {
            "id": record.id,
            "request_id": record.request_id,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "user_id": record.user_id,
            "action": record.action,
            "outcome": record.outcome,
            "status_code": record.status_code,
            "old_value": record.old_value,
            "new_value": record.new_value,
        }
        for record in records
    ]
