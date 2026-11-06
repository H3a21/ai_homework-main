"""Idempotent lifecycle updates for multi-submission grading batches."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GradingBatch, GradingBatchItem


TERMINAL_ITEM_STATUSES = ("completed", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def start_batch_item(
    db: AsyncSession,
    batch_id: int,
    submission_id: int,
) -> GradingBatchItem:
    item = (
        await db.execute(
            select(GradingBatchItem)
            .where(
                GradingBatchItem.batch_id == batch_id,
                GradingBatchItem.submission_id == submission_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise ValueError(
            f"Batch item not found for batch={batch_id}, submission={submission_id}"
        )

    batch = (
        await db.execute(
            select(GradingBatch)
            .where(GradingBatch.id == batch_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not batch:
        raise ValueError(f"Grading batch {batch_id} not found")

    if item.status == "queued":
        item.status = "grading"
        item.started_at = _now()
    if batch.status == "pending":
        batch.status = "grading"
    await db.commit()
    return item


async def finish_batch_item(
    db: AsyncSession,
    batch_id: int,
    submission_id: int,
    status: str,
    error: Exception | None = None,
) -> GradingBatch:
    if status not in TERMINAL_ITEM_STATUSES:
        raise ValueError(f"Invalid terminal batch item status: {status}")

    item = (
        await db.execute(
            select(GradingBatchItem)
            .where(
                GradingBatchItem.batch_id == batch_id,
                GradingBatchItem.submission_id == submission_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise ValueError(
            f"Batch item not found for batch={batch_id}, submission={submission_id}"
        )

    batch = (
        await db.execute(
            select(GradingBatch)
            .where(GradingBatch.id == batch_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not batch:
        raise ValueError(f"Grading batch {batch_id} not found")

    if item.status in TERMINAL_ITEM_STATUSES:
        await db.rollback()
        return batch

    item.status = status
    item.error_message = str(error)[:2000] if error else None
    item.completed_at = _now()
    await db.flush()

    completed = await db.scalar(
        select(func.count(GradingBatchItem.id)).where(
            GradingBatchItem.batch_id == batch_id,
            GradingBatchItem.status == "completed",
        )
    )
    failed = await db.scalar(
        select(func.count(GradingBatchItem.id)).where(
            GradingBatchItem.batch_id == batch_id,
            GradingBatchItem.status == "failed",
        )
    )
    batch.completed_submissions = int(completed or 0)
    batch.failed_submissions = int(failed or 0)

    finished = batch.completed_submissions + batch.failed_submissions
    if finished >= batch.total_submissions:
        batch.status = "failed" if batch.failed_submissions else "completed"
        batch.error_message = (
            f"{batch.failed_submissions} submission(s) failed"
            if batch.failed_submissions
            else None
        )
        batch.completed_at = _now()
    else:
        batch.status = "grading"

    await db.commit()
    return batch
