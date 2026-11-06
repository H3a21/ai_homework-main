"""Regression tests for the legacy deterministic grading fallback."""

import asyncio
from types import SimpleNamespace

import pytest

from app import grading
from app.models import Assignment, Question, Submission, SubmissionImage


class Result:
    def __init__(self, scalar=None, scalars=None):
        self.scalar = scalar
        self.values = scalars or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.values)


class DB:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


def test_legacy_helpers_cover_empty_and_bounded_inputs(monkeypatch):
    monkeypatch.setattr(grading.random, "choice", lambda values: values[0])
    assert grading._simple_text_match("a b", "ab") == 1.0
    assert grading._simple_text_match("anything", "") == 0.5
    assert grading._pick_comment()
    assert grading._get_feedback(1, 10, 10)
    assert grading._get_feedback(1, 10, 7)
    assert grading._get_feedback(1, 10, 1)


def test_mock_grade_scores_cached_ocr_text_and_zero_score_questions(monkeypatch):
    submission = Submission(id=3, assignment_id=2, student_id=8, status="pending")
    assignment = Assignment(id=2, class_id=1, subject_id=1, teacher_id=5)
    questions = [
        Question(id=1, assignment_id=2, question_number=1, content="hello", max_score=10),
        Question(id=2, assignment_id=2, question_number=2, content="ignored", max_score=0),
    ]
    image = SubmissionImage(
        id=4, submission_id=3, image_path="answer.png", page_number=1, recognized_text="hello"
    )
    db = DB([
        Result(scalar=submission), Result(scalar=assignment),
        Result(scalars=questions), Result(scalars=[image]),
    ])
    monkeypatch.setattr(grading.random, "choice", lambda values: values[0])

    asyncio.run(grading.mock_grade(db, 3))
    assert submission.status == "completed"
    assert float(submission.total_score) == 10.0
    assert len(db.added) == 2
    assert db.added[1].score == 0.0
    assert db.commits == 1


def test_mock_grade_uses_ocr_service_for_uncached_images(monkeypatch):
    submission = Submission(id=3, assignment_id=2, student_id=8, status="pending")
    assignment = Assignment(id=2, class_id=1, subject_id=1, teacher_id=5)
    question = Question(id=1, assignment_id=2, question_number=1, content="hello", max_score=10)
    image = SubmissionImage(id=4, submission_id=3, image_path="answer.png", page_number=1)
    db = DB([
        Result(scalar=submission), Result(scalar=assignment),
        Result(scalars=[question]), Result(scalars=[image]),
    ])

    async def fake_ocr(data, filename):
        return {"text": "hello"}

    monkeypatch.setattr(grading, "OCR_AVAILABLE", True)
    monkeypatch.setattr(grading, "ocr_image", fake_ocr)
    monkeypatch.setattr(
        grading,
        "read_image_source",
        lambda path: asyncio.sleep(
            0,
            result=SimpleNamespace(content=b"image", content_type="image/png"),
        ),
    )
    monkeypatch.setattr(grading.random, "choice", lambda values: values[0])

    asyncio.run(grading.mock_grade(db, 3))
    assert image.recognized_text == "hello"
    assert submission.status == "completed"


def test_mock_grade_rejects_missing_records_and_skips_completed():
    async def run():
        with pytest.raises(ValueError, match="Submission 3 not found"):
            await grading.mock_grade(DB([Result()]), 3)

        missing_assignment = Submission(id=3, assignment_id=2, student_id=8, status="pending")
        with pytest.raises(ValueError, match="Assignment 2 not found"):
            await grading.mock_grade(DB([Result(scalar=missing_assignment), Result()]), 3)

        completed = Submission(id=3, assignment_id=2, student_id=8, status="completed")
        assert await grading.mock_grade(DB([Result(scalar=completed)]), 3) is None

    asyncio.run(run())
