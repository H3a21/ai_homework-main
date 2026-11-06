"""Unit tests for scoped batch creation and query responses."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import Assignment, GradingBatch, GradingBatchItem, Submission
from app.routers import grading_batches as router


class Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class Result:
    def __init__(self, scalar=None, scalars=None):
        self.scalar = scalar
        self.values = scalars or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return Scalars(self.values)


class DB:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        batch = next(value for value in self.added if isinstance(value, GradingBatch))
        batch.id = 9

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        if isinstance(value, GradingBatchItem) and value.id is None:
            value.id = value.submission_id + 100


@pytest.fixture(autouse=True)
def stub_batch_events(monkeypatch):
    async def publish(*args):
        return True

    monkeypatch.setattr(router, "publish_batch_status", publish)


def test_create_batch_enqueues_each_pending_submission(monkeypatch):
    assignment = Assignment(id=4, class_id=2, teacher_id=5)
    submissions = [
        Submission(id=11, assignment_id=4, status="pending"),
        Submission(id=12, assignment_id=4, status="pending"),
    ]
    db = DB([
        Result(scalar=assignment),
        Result(),
        Result(scalars=submissions),
    ])
    calls = []

    async def allow(*args):
        return None

    monkeypatch.setattr(router, "require_class_teacher", allow)
    monkeypatch.setattr(
        router,
        "enqueue_grade_submission",
        lambda submission_id, batch_id: calls.append((submission_id, batch_id))
        or f"task-{submission_id}",
    )

    async def run():
        result = await router.create_grading_batch(
            router.CreateGradingBatchRequest(assignment_id=4),
            db,
            SimpleNamespace(id=5, role="teacher"),
        )
        assert result["id"] == 9
        assert result["total_submissions"] == 2
        assert result["queued_submissions"] == 2
        assert calls == [(11, 9), (12, 9)]
        assert all(submission.status == "grading" for submission in submissions)
        assert db.commits == 3

    asyncio.run(run())


def test_create_batch_rejects_active_or_empty_assignment(monkeypatch):
    assignment = Assignment(id=4, class_id=2, teacher_id=5)

    async def allow(*args):
        return None

    monkeypatch.setattr(router, "require_class_teacher", allow)

    async def run():
        active = GradingBatch(id=8, assignment_id=4, status="grading")
        with pytest.raises(HTTPException) as conflict:
            await router.create_grading_batch(
                router.CreateGradingBatchRequest(assignment_id=4),
                DB([Result(scalar=assignment), Result(scalar=active)]),
                SimpleNamespace(id=5),
            )
        assert conflict.value.status_code == 409

        with pytest.raises(HTTPException) as empty:
            await router.create_grading_batch(
                router.CreateGradingBatchRequest(assignment_id=4),
                DB([Result(scalar=assignment), Result(), Result(scalars=[])]),
                SimpleNamespace(id=5),
            )
        assert empty.value.status_code == 409

    asyncio.run(run())


def test_create_batch_isolates_one_enqueue_failure(monkeypatch):
    assignment = Assignment(id=4, class_id=2, teacher_id=5)
    submissions = [
        Submission(id=11, assignment_id=4, status="pending"),
        Submission(id=12, assignment_id=4, status="pending"),
    ]
    db = DB([
        Result(scalar=assignment),
        Result(),
        Result(scalars=submissions),
    ])

    async def allow(*args):
        return None

    def enqueue(submission_id, batch_id):
        if submission_id == 11:
            raise RuntimeError("broker unavailable")
        return "task-12"

    async def mark_failed(db, batch_id, submission_id, status, error):
        batch = next(value for value in db.added if isinstance(value, GradingBatch))
        item = next(
            value
            for value in db.added
            if isinstance(value, GradingBatchItem)
            and value.submission_id == submission_id
        )
        item.status = status
        item.error_message = str(error)
        batch.failed_submissions = 1
        return batch

    monkeypatch.setattr(router, "require_class_teacher", allow)
    monkeypatch.setattr(router, "enqueue_grade_submission", enqueue)
    monkeypatch.setattr(router, "finish_batch_item", mark_failed)

    async def run():
        result = await router.create_grading_batch(
            router.CreateGradingBatchRequest(assignment_id=4),
            db,
            SimpleNamespace(id=5),
        )
        assert submissions[0].status == "pending"
        assert submissions[1].status == "grading"
        assert result["failed_submissions"] == 1
        assert result["items"][0]["error_message"] == "broker unavailable"
        assert result["items"][1]["task_id"] == "task-12"

    asyncio.run(run())


def test_batch_detail_requires_managed_assignment(monkeypatch):
    batch = GradingBatch(id=8, assignment_id=4, status="completed")
    assignment = Assignment(id=4, class_id=2, teacher_id=5)

    async def deny(*args):
        raise HTTPException(status_code=403, detail="forbidden")

    monkeypatch.setattr(router, "require_class_teacher", deny)

    async def run():
        with pytest.raises(HTTPException) as forbidden:
            await router.get_grading_batch(
                8,
                DB([Result(scalar=batch), Result(scalar=assignment)]),
                SimpleNamespace(id=7),
            )
        assert forbidden.value.status_code == 403

    asyncio.run(run())


def test_batch_list_and_detail_return_progress(monkeypatch):
    batch = GradingBatch(
        id=8,
        assignment_id=4,
        teacher_id=5,
        total_submissions=2,
        completed_submissions=1,
        failed_submissions=0,
        status="grading",
    )
    assignment = Assignment(id=4, class_id=2, teacher_id=5)
    items = [
        GradingBatchItem(id=20, batch_id=8, submission_id=11, status="completed"),
        GradingBatchItem(id=21, batch_id=8, submission_id=12, status="grading"),
    ]

    async def allow(*args):
        return None

    monkeypatch.setattr(router, "require_class_teacher", allow)

    async def run():
        listed = await router.list_grading_batches(
            assignment_id=4,
            limit=1,
            db=DB([Result(scalars=[batch])]),
            user=SimpleNamespace(id=5),
        )
        assert listed[0]["progress_percent"] == 50.0

        detail = await router.get_grading_batch(
            8,
            DB([
                Result(scalar=batch),
                Result(scalar=assignment),
                Result(scalars=items),
            ]),
            SimpleNamespace(id=5),
        )
        assert detail["grading_submissions"] == 1
        assert detail["items"][0]["status"] == "completed"

    asyncio.run(run())
