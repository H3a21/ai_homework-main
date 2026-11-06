"""Unit tests for resource-scoped grading and audit history APIs."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import Assignment, AuditLog, GradingAttempt, Submission
from app.routers import history


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
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, statement):
        if not self.results:
            raise AssertionError("Unexpected database query")
        return self.results.pop(0)


def test_teacher_reads_versioned_attempts_for_managed_submission():
    teacher = SimpleNamespace(id=5, role="teacher")
    submission = Submission(id=4, assignment_id=2, student_id=8)
    assignment = Assignment(id=2, class_id=1)
    attempt = GradingAttempt(
        id=9,
        submission_id=4,
        attempt_number=2,
        status="completed",
        total_score=8,
        grader_version="1.0.0",
        duration_ms=125,
    )

    async def run():
        result = await history.list_grading_attempts(
            4,
            FakeDB([
                FakeResult(submission),
                FakeResult(assignment),
                FakeResult(1),
                FakeResult(scalars=[attempt]),
            ]),
            teacher,
        )
        assert result[0]["attempt_number"] == 2
        assert result[0]["total_score"] == 8.0
        assert result[0]["duration_ms"] == 125

    asyncio.run(run())


def test_teacher_reads_sanitized_submission_audit():
    teacher = SimpleNamespace(id=5, role="teacher")
    submission = Submission(id=4, assignment_id=2, student_id=8)
    assignment = Assignment(id=2, class_id=1)
    record = AuditLog(
        id=10,
        request_id="request-1",
        timestamp=datetime(2026, 7, 19),
        user_id=5,
        action="submission.grade",
        resource_type="submission",
        resource_id=4,
        outcome="success",
        method="POST",
        path="/api/submissions/4/grade",
        status_code=202,
        ip_address="127.0.0.1",
        user_agent="private-agent",
    )

    async def run():
        result = await history.list_submission_audit(
            4,
            FakeDB([
                FakeResult(submission),
                FakeResult(assignment),
                FakeResult(1),
                FakeResult(scalars=[record]),
            ]),
            teacher,
        )
        assert result[0]["action"] == "submission.grade"
        assert "ip_address" not in result[0]
        assert "user_agent" not in result[0]

    asyncio.run(run())


def test_unmanaged_teacher_cannot_read_submission_history():
    teacher = SimpleNamespace(id=6, role="teacher")
    submission = Submission(id=4, assignment_id=2, student_id=8)
    assignment = Assignment(id=2, class_id=1)

    async def run():
        with pytest.raises(HTTPException) as forbidden:
            await history.list_grading_attempts(
                4,
                FakeDB([
                    FakeResult(submission),
                    FakeResult(assignment),
                    FakeResult(),
                ]),
                teacher,
            )
        assert forbidden.value.status_code == 403

    asyncio.run(run())


def test_history_returns_explicit_missing_resource_errors():
    teacher = SimpleNamespace(id=5, role="teacher")

    async def run():
        with pytest.raises(HTTPException) as missing_submission:
            await history.list_grading_attempts(
                99,
                FakeDB([FakeResult()]),
                teacher,
            )
        assert missing_submission.value.status_code == 404

        submission = Submission(id=4, assignment_id=99, student_id=8)
        with pytest.raises(HTTPException) as missing_assignment:
            await history.list_grading_attempts(
                4,
                FakeDB([FakeResult(submission), FakeResult()]),
                teacher,
            )
        assert missing_assignment.value.status_code == 404

    asyncio.run(run())
