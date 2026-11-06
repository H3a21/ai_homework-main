import asyncio
import logging
import time

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.grading_batches import finish_batch_item, start_batch_item
from app.grading_history import (
    best_effort_complete,
    create_attempt,
    fail_attempt,
    skip_attempt,
)
from app.observability import (
    GRADING_DURATION,
    GRADING_RETRIES,
    GRADING_TASKS,
    configure_logging,
)
from app.submission_events import publish_batch_status, publish_submission_status


configure_logging("celery-worker")
worker_logger = logging.getLogger("app.worker")

celery_app = Celery(
    "grader",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.task_routes = {
    "grade_submission": {"queue": "grading"},
    "generate_report": {"queue": "report"},
}
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.worker_hijack_root_logger = False


def _record_grading_attempt(
    submission_id: int,
    subject: str,
    task_status: str,
    duration: float,
) -> None:
    GRADING_TASKS.labels(subject=subject, status=task_status).inc()
    GRADING_DURATION.labels(subject=subject).observe(duration)
    worker_logger.info(
        "grading_attempt_completed",
        extra={
            "submission_id": submission_id,
            "subject": subject,
            "task_status": task_status,
            "duration_ms": round(duration * 1000, 2),
        },
    )


async def _execute_grade_submission(
    submission_id: int,
    batch_id: int | None = None,
) -> dict:
    """Run one grading attempt in an isolated async engine/session."""
    from app.grade_assignment import grade_submission
    from app.models import Assignment, Subject, Submission

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    started_at = time.perf_counter()
    subject = "unknown"
    task_status = "failed"
    attempt_id = None

    try:
        async with session_factory() as db:
            result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            submission = result.scalar_one_or_none()
            if not submission:
                raise ValueError(f"Submission {submission_id} not found")

            if batch_id is not None:
                await start_batch_item(db, batch_id, submission_id)

            assignment_result = await db.execute(
                select(Assignment).where(Assignment.id == submission.assignment_id)
            )
            assignment = assignment_result.scalar_one_or_none()
            if assignment:
                subject_result = await db.execute(
                    select(Subject).where(Subject.id == assignment.subject_id)
                )
                subject_record = subject_result.scalar_one_or_none()
                if subject_record:
                    from app.grade_assignment import resolve_grading_pipeline

                    subject = resolve_grading_pipeline(subject_record.name)

            attempt = await create_attempt(db, submission_id)

            if submission.status == "completed":
                task_status = "skipped"
                await skip_attempt(
                    db,
                    attempt,
                    submission,
                    round((time.perf_counter() - started_at) * 1000),
                )
                await publish_submission_status(submission_id, "completed")
                if batch_id is not None:
                    batch = await finish_batch_item(
                        db,
                        batch_id,
                        submission_id,
                        "completed",
                    )
                    await publish_batch_status(
                        batch.id,
                        batch.status,
                        batch.total_submissions,
                        batch.completed_submissions,
                        batch.failed_submissions,
                    )
                return {"status": "completed", "submission_id": submission_id}

            submission.status = "grading"
            await db.commit()
            attempt_id = attempt.id
            await publish_submission_status(submission_id, "grading")

            try:
                await grade_submission(db, submission_id)
            except Exception as exc:
                await db.rollback()
                pending_result = await db.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
                pending_submission = pending_result.scalar_one_or_none()
                if pending_submission and pending_submission.status == "grading":
                    pending_submission.status = "pending"
                    await db.commit()
                    await publish_submission_status(
                        submission_id, "pending", reason="retrying"
                    )
                if attempt_id is not None:
                    try:
                        await fail_attempt(
                            db,
                            attempt_id,
                            exc,
                            round((time.perf_counter() - started_at) * 1000),
                        )
                    except Exception:
                        await db.rollback()
                        worker_logger.warning(
                            "grading_history_failure_record_failed",
                            extra={"submission_id": submission_id},
                            exc_info=True,
                        )
                raise

            task_status = "completed"
            await best_effort_complete(
                db,
                attempt,
                submission,
                round((time.perf_counter() - started_at) * 1000),
            )
            await publish_submission_status(submission_id, "completed")
            if batch_id is not None:
                batch = await finish_batch_item(
                    db,
                    batch_id,
                    submission_id,
                    "completed",
                )
                await publish_batch_status(
                    batch.id,
                    batch.status,
                    batch.total_submissions,
                    batch.completed_submissions,
                    batch.failed_submissions,
                )
            return {"status": "completed", "submission_id": submission_id}
    except Exception:
        task_status = "failed"
        raise
    finally:
        duration = time.perf_counter() - started_at
        _record_grading_attempt(submission_id, subject, task_status, duration)
        await engine.dispose()


async def _finish_failed_batch_item(
    batch_id: int,
    submission_id: int,
    error: Exception,
) -> None:
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            batch = await finish_batch_item(
                db,
                batch_id,
                submission_id,
                "failed",
                error,
            )
            await publish_batch_status(
                batch.id,
                batch.status,
                batch.total_submissions,
                batch.completed_submissions,
                batch.failed_submissions,
            )
    finally:
        await engine.dispose()


def _record_failed_batch_item(
    batch_id: int,
    submission_id: int,
    error: Exception,
) -> None:
    try:
        asyncio.run(_finish_failed_batch_item(batch_id, submission_id, error))
    except Exception:
        worker_logger.exception(
            "grading_batch_failure_record_failed",
            extra={"batch_id": batch_id, "submission_id": submission_id},
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="grade_submission")
def grade_submission_task(
    self,
    submission_id: int,
    batch_id: int | None = None,
):
    try:
        return asyncio.run(_execute_grade_submission(submission_id, batch_id))
    except ValueError as exc:
        if batch_id is not None:
            _record_failed_batch_item(batch_id, submission_id, exc)
        worker_logger.error(
            "grading_task_rejected",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "submission_id": submission_id,
                "task_status": "failed",
            },
        )
        raise
    except Exception as exc:
        GRADING_RETRIES.labels(subject="unknown").inc()
        worker_logger.warning(
            "grading_task_retrying",
            extra={
                "task_id": getattr(getattr(self, "request", None), "id", None),
                "submission_id": submission_id,
                "task_status": "retry",
            },
            exc_info=exc,
        )
        retries = getattr(getattr(self, "request", None), "retries", 0)
        max_retries = getattr(self, "max_retries", 3)
        if batch_id is not None and retries >= max_retries:
            _record_failed_batch_item(batch_id, submission_id, exc)
            raise
        raise self.retry(exc=exc)


def enqueue_grade_submission(
    submission_id: int,
    batch_id: int | None = None,
) -> str:
    if batch_id is None:
        task = grade_submission_task.delay(submission_id)
    else:
        task = grade_submission_task.delay(submission_id, batch_id)
    return task.id


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="generate_report")
def generate_report(self, class_id: int, week: str):
    return {"status": "pending", "class_id": class_id, "week": week}
