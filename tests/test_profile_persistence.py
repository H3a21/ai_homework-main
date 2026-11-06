"""Unit tests for mastery persistence and learning report database loaders."""

import asyncio
from types import SimpleNamespace

from app.knowledge_profile import update_mastery_for_results
from app.learning_reports import load_class_report, load_student_report
from app.models import (
    Class,
    GradingResult,
    KnowledgePoint,
    Question,
    StudentKnowledgeMastery,
    Subject,
    User,
)


class Result:
    def __init__(self, scalar=None, scalars=None, rows=None):
        self.scalar = scalar
        self.scalar_values = scalars or []
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalar_values)

    def all(self):
        return self.rows


class DB:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.flushes = 0

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1


def test_update_mastery_creates_and_updates_one_record_per_point():
    question = Question(
        id=1,
        assignment_id=2,
        question_number=1,
        max_score=10,
        knowledge_point_id=5,
        difficulty=0.5,
        discrimination=1.2,
    )
    grading_results = [
        GradingResult(question_id=1, score=8),
        GradingResult(question_id=1, score=6),
        GradingResult(question_id=99, score=10),
    ]
    db = DB([Result(scalar=None)])

    updated = asyncio.run(
        update_mastery_for_results(db, 8, {1: question}, grading_results)
    )
    assert updated == 1
    assert db.flushes == 1
    record = db.added[0]
    assert record.student_id == 8
    assert record.knowledge_point_id == 5
    assert record.attempt_count == 2
    assert float(record.success_sum) == 1.4


def test_update_mastery_reuses_existing_record():
    question = Question(
        id=1,
        assignment_id=2,
        question_number=1,
        max_score=10,
        knowledge_point_id=5,
        difficulty=0,
        discrimination=1,
    )
    record = StudentKnowledgeMastery(
        student_id=8,
        knowledge_point_id=5,
        mastery_level=0.5,
        ability_theta=0,
        attempt_count=1,
        success_sum=0.5,
    )
    db = DB([Result(scalar=record)])
    updated = asyncio.run(
        update_mastery_for_results(
            db, 8, {1: question}, [GradingResult(question_id=1, score=10)]
        )
    )
    assert updated == 1
    assert db.added == []
    assert record.attempt_count == 2


def test_load_student_report_normalizes_database_rows():
    student = User(
        id=8, username="student", password_hash="x", display_name="Student", role="student"
    )
    point = KnowledgePoint(id=5, subject_id=1, name="Fractions")
    subject = Subject(id=1, name="math")
    mastery = StudentKnowledgeMastery(
        student_id=8, knowledge_point_id=5, mastery_level=0.75,
        ability_theta=0.4, attempt_count=2, success_sum=1.5,
    )
    db = DB([
        Result(scalar=student),
        Result(rows=[(mastery, point, subject)]),
    ])
    report = asyncio.run(load_student_report(db, 8, 1))
    assert report["student_id"] == 8
    assert report["overview"]["average_mastery"] == 0.75
    assert report["radar"][0]["knowledge_point_name"] == "Fractions"

    assert asyncio.run(load_student_report(DB([Result()]), 99)) is None


def test_load_class_report_includes_students_and_mastery_rows():
    classroom = Class(id=2, name="Class A", grade="6", invite_code="ABC")
    student = User(
        id=8, username="student", password_hash="x", display_name="Student", role="student"
    )
    point = KnowledgePoint(id=5, subject_id=1, name="Fractions")
    subject = Subject(id=1, name="math")
    mastery = StudentKnowledgeMastery(
        student_id=8, knowledge_point_id=5, mastery_level=0.5,
        ability_theta=0, attempt_count=2, success_sum=1,
    )
    db = DB([
        Result(scalar=classroom),
        Result(scalars=[student]),
        Result(rows=[(mastery, point, subject, student)]),
    ])
    report = asyncio.run(load_class_report(db, 2, 1))
    assert report["class_id"] == 2
    assert report["overview"]["student_count"] == 1
    assert report["student_summaries"][0]["student_id"] == 8

    assert asyncio.run(load_class_report(DB([Result()]), 99)) is None
