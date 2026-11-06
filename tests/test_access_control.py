"""Unit tests for object-level authorization rules."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.access_control import (
    require_assignment_access,
    require_class_access,
    require_class_teacher,
    require_submission_access,
    require_teacher_student_access,
)
from app.models import Assignment, Submission


class FakeResult:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)

    async def execute(self, statement):
        if not self.results:
            raise AssertionError("Unexpected database query in unit test")
        return self.results.pop(0)


def test_class_and_assignment_access_require_membership():
    teacher = SimpleNamespace(id=5, role="teacher")
    student = SimpleNamespace(id=8, role="student")
    assignment = Assignment(id=2, class_id=1)

    async def run():
        await require_class_access(FakeDB(FakeResult(1)), teacher, 1)
        await require_class_access(FakeDB(FakeResult(2)), student, 1)
        await require_assignment_access(FakeDB(FakeResult(3)), student, assignment)

        with pytest.raises(HTTPException) as forbidden:
            await require_class_teacher(FakeDB(FakeResult()), teacher.id, 2)
        assert forbidden.value.status_code == 403

    asyncio.run(run())


def test_submission_access_is_scoped_to_owner_or_managed_class():
    assignment = Assignment(id=2, class_id=1)
    submission = Submission(id=4, assignment_id=2, student_id=8)

    async def run():
        await require_submission_access(
            FakeDB(), SimpleNamespace(id=8, role="student"), submission, assignment
        )
        await require_submission_access(
            FakeDB(FakeResult(1)),
            SimpleNamespace(id=5, role="teacher"),
            submission,
            assignment,
        )

        with pytest.raises(HTTPException) as other_student:
            await require_submission_access(
                FakeDB(),
                SimpleNamespace(id=9, role="student"),
                submission,
                assignment,
            )
        assert other_student.value.status_code == 403

        with pytest.raises(HTTPException) as unrelated_teacher:
            await require_submission_access(
                FakeDB(FakeResult()),
                SimpleNamespace(id=6, role="teacher"),
                submission,
                assignment,
            )
        assert unrelated_teacher.value.status_code == 403

    asyncio.run(run())


def test_teacher_student_access_requires_a_shared_managed_class():
    async def run():
        await require_teacher_student_access(FakeDB(FakeResult(1)), 5, 8)

        with pytest.raises(HTTPException) as forbidden:
            await require_teacher_student_access(FakeDB(FakeResult()), 5, 9)
        assert forbidden.value.status_code == 403

    asyncio.run(run())
