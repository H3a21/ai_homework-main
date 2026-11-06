"""Unit tests for idempotent grading batch lifecycle updates."""

import asyncio

import pytest

from app import grading_batches
from app.models import GradingBatch, GradingBatchItem


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class DB:
    def __init__(self, results=None, scalars=None):
        self.results = list(results or [])
        self.scalars = list(scalars or [])
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def execute(self, statement):
        return Result(self.results.pop(0))

    async def scalar(self, statement):
        return self.scalars.pop(0)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_start_batch_item_transitions_queued_batch():
    batch = GradingBatch(id=3, status="pending")
    item = GradingBatchItem(batch_id=3, submission_id=7, status="queued")

    async def run():
        db = DB([item, batch])
        result = await grading_batches.start_batch_item(db, 3, 7)
        assert result is item
        assert item.status == "grading"
        assert item.started_at is not None
        assert batch.status == "grading"
        assert db.commits == 1

    asyncio.run(run())


def test_finish_batch_item_aggregates_terminal_status():
    batch = GradingBatch(
        id=3,
        total_submissions=2,
        completed_submissions=0,
        failed_submissions=0,
        status="grading",
    )
    item = GradingBatchItem(batch_id=3, submission_id=7, status="grading")

    async def run():
        db = DB([item, batch], scalars=[1, 1])
        result = await grading_batches.finish_batch_item(
            db,
            3,
            7,
            "failed",
            RuntimeError("OCR unavailable"),
        )
        assert result is batch
        assert item.status == "failed"
        assert item.error_message == "OCR unavailable"
        assert batch.completed_submissions == 1
        assert batch.failed_submissions == 1
        assert batch.status == "failed"
        assert batch.completed_at is not None
        assert db.flushes == db.commits == 1

    asyncio.run(run())


def test_finish_batch_item_is_idempotent_and_validates_status():
    batch = GradingBatch(id=3, total_submissions=1, status="completed")
    item = GradingBatchItem(batch_id=3, submission_id=7, status="completed")

    async def run():
        db = DB([item, batch])
        assert await grading_batches.finish_batch_item(db, 3, 7, "completed") is batch
        assert db.rollbacks == 1
        assert db.commits == 0

        with pytest.raises(ValueError, match="Invalid terminal"):
            await grading_batches.finish_batch_item(DB(), 3, 7, "grading")

    asyncio.run(run())


def test_batch_lifecycle_rejects_missing_records():
    item = GradingBatchItem(batch_id=3, submission_id=7, status="queued")

    async def run():
        with pytest.raises(ValueError, match="Batch item not found"):
            await grading_batches.start_batch_item(DB([None]), 3, 7)
        with pytest.raises(ValueError, match="Grading batch 3 not found"):
            await grading_batches.start_batch_item(DB([item, None]), 3, 7)
        with pytest.raises(ValueError, match="Batch item not found"):
            await grading_batches.finish_batch_item(
                DB([None]), 3, 7, "completed"
            )
        with pytest.raises(ValueError, match="Grading batch 3 not found"):
            await grading_batches.finish_batch_item(
                DB([item, None]), 3, 7, "completed"
            )

    asyncio.run(run())


def test_finish_batch_item_keeps_partially_finished_batch_running():
    batch = GradingBatch(
        id=3,
        total_submissions=2,
        completed_submissions=0,
        failed_submissions=0,
        status="grading",
    )
    item = GradingBatchItem(batch_id=3, submission_id=7, status="grading")

    async def run():
        db = DB([item, batch], scalars=[1, 0])
        result = await grading_batches.finish_batch_item(
            db, 3, 7, "completed"
        )
        assert result.status == "grading"
        assert result.completed_at is None
        assert item.error_message is None

    asyncio.run(run())
