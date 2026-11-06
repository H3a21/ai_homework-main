"""Unit tests for versioned grading attempt snapshots."""

import asyncio

from app import grading_history
from app.models import GradingAttempt, GradingResult, Submission, SubmissionImage


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, scalar=None, scalars=None):
        self.scalar = scalar
        self.values = scalars or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return FakeScalars(self.values)


class FakeDB:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_create_attempt_increments_submission_version():
    async def run():
        db = FakeDB([FakeResult(scalar=2)])
        attempt = await grading_history.create_attempt(db, 42)
        assert attempt.submission_id == 42
        assert attempt.attempt_number == 3
        assert attempt.status == "started"
        assert db.added == [attempt]

    asyncio.run(run())


def test_complete_attempt_captures_ocr_and_question_results():
    attempt = GradingAttempt(id=5, submission_id=42, attempt_number=1)
    submission = Submission(
        id=42,
        total_score=8,
        comment="Good progress",
        status="completed",
    )
    image = SubmissionImage(page_number=1, recognized_text="2+2=4")
    result = GradingResult(question_id=7, score=8, feedback="Correct")

    async def run():
        db = FakeDB([
            FakeResult(scalars=[image]),
            FakeResult(scalars=[result]),
        ])
        await grading_history.complete_attempt(db, attempt, submission, 125)
        assert attempt.status == "completed"
        assert attempt.raw_ocr_result["pages"][0]["recognized_text"] == "2+2=4"
        assert attempt.result_snapshot["questions"][0] == {
            "question_id": 7,
            "score": 8.0,
            "feedback": "Correct",
        }
        assert attempt.duration_ms == 125
        assert db.commits == 1

    asyncio.run(run())


def test_fail_and_skip_attempt_record_terminal_state():
    failed = GradingAttempt(id=5, submission_id=42, attempt_number=1)
    skipped = GradingAttempt(id=6, submission_id=42, attempt_number=2)
    submission = Submission(id=42, total_score=9, status="completed")

    async def run():
        fail_db = FakeDB([FakeResult(scalar=failed)])
        await grading_history.fail_attempt(
            fail_db,
            5,
            RuntimeError("temporary failure"),
            50,
        )
        assert failed.status == "failed"
        assert failed.error_message == "temporary failure"

        skip_db = FakeDB()
        await grading_history.skip_attempt(skip_db, skipped, submission, 3)
        assert skipped.status == "skipped"
        assert float(skipped.total_score) == 9.0
        assert skipped.duration_ms == 3

    asyncio.run(run())


def test_missing_attempt_and_best_effort_failure_are_isolated(monkeypatch):
    submission = Submission(id=42, status="completed")
    attempt = GradingAttempt(id=5, submission_id=42, attempt_number=1)

    async def fail_complete(*args):
        raise RuntimeError("snapshot unavailable")

    monkeypatch.setattr(grading_history, "complete_attempt", fail_complete)

    async def run():
        missing_db = FakeDB([FakeResult()])
        await grading_history.fail_attempt(
            missing_db,
            999,
            RuntimeError("ignored"),
            10,
        )
        assert missing_db.commits == 0

        failing_db = FakeDB()
        assert await grading_history.best_effort_complete(
            failing_db,
            attempt,
            submission,
            20,
        ) is False
        assert failing_db.rollbacks == 1

    asyncio.run(run())
