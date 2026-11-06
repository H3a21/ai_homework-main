"""Versioned snapshots for every grading task attempt."""

from datetime import datetime, timezone
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    GradingAttempt,
    GradingResult,
    Submission,
    SubmissionImage,
)


logger = logging.getLogger(__name__)


def _completed_at() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_attempt(
    db: AsyncSession,
    submission_id: int,
) -> GradingAttempt:
    latest = await db.execute(
        select(func.max(GradingAttempt.attempt_number)).where(
            GradingAttempt.submission_id == submission_id
        )
    )
    attempt = GradingAttempt(
        submission_id=submission_id,
        attempt_number=int(latest.scalar_one_or_none() or 0) + 1,
        status="started",
        grader_version=settings.GRADER_VERSION,
    )
    db.add(attempt)
    return attempt


async def complete_attempt(
    db: AsyncSession,
    attempt: GradingAttempt,
    submission: Submission,
    duration_ms: int,
) -> None:
    images = (
        await db.execute(
            select(SubmissionImage)
            .where(SubmissionImage.submission_id == submission.id)
            .order_by(SubmissionImage.page_number)
        )
    ).scalars().all()
    results = (
        await db.execute(
            select(GradingResult)
            .where(GradingResult.submission_id == submission.id)
            .order_by(GradingResult.question_id, GradingResult.id)
        )
    ).scalars().all()

    attempt.status = "completed"
    attempt.total_score = submission.total_score
    attempt.raw_ocr_result = {
        "pages": [
            {
                "page_number": image.page_number,
                "recognized_text": image.recognized_text or "",
            }
            for image in images
        ]
    }
    attempt.result_snapshot = {
        "total_score": float(submission.total_score)
        if submission.total_score is not None
        else None,
        "comment": submission.comment,
        "questions": [
            {
                "question_id": result.question_id,
                "score": float(result.score) if result.score is not None else None,
                "feedback": result.feedback,
            }
            for result in results
        ],
    }
    attempt.duration_ms = duration_ms
    attempt.completed_at = _completed_at()
    await db.commit()


async def skip_attempt(
    db: AsyncSession,
    attempt: GradingAttempt,
    submission: Submission,
    duration_ms: int,
) -> None:
    attempt.status = "skipped"
    attempt.total_score = submission.total_score
    attempt.duration_ms = duration_ms
    attempt.completed_at = _completed_at()
    await db.commit()


async def fail_attempt(
    db: AsyncSession,
    attempt_id: int,
    error: Exception,
    duration_ms: int,
) -> None:
    attempt = (
        await db.execute(
            select(GradingAttempt).where(GradingAttempt.id == attempt_id)
        )
    ).scalar_one_or_none()
    if not attempt:
        return
    attempt.status = "failed"
    attempt.error_message = str(error)[:2000]
    attempt.duration_ms = duration_ms
    attempt.completed_at = _completed_at()
    await db.commit()


async def best_effort_complete(
    db: AsyncSession,
    attempt: GradingAttempt,
    submission: Submission,
    duration_ms: int,
) -> bool:
    try:
        await complete_attempt(db, attempt, submission, duration_ms)
        return True
    except Exception:
        await db.rollback()
        logger.warning(
            "grading_history_completion_failed",
            extra={"submission_id": submission.id},
            exc_info=True,
        )
        return False
