"""Unit tests for grading orchestration and Celery failure handling."""

import asyncio
from types import SimpleNamespace

import pytest

from app import grade_assignment, worker
from app.models import Assignment, Question, Subject, Submission, SubmissionImage


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
        if not self.results:
            raise AssertionError("Unexpected database query")
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def test_feedback_and_pipeline_helpers_cover_boundaries():
    assert grade_assignment.resolve_grading_pipeline(None) == "default"
    assert grade_assignment.resolve_grading_pipeline("mathematics") == "math"
    assert grade_assignment._get_feedback(1, 10, 10)
    assert grade_assignment._get_feedback(1, 10, 7)
    assert grade_assignment._get_feedback(1, 10, 2)


def test_subject_pipelines_return_bounded_results():
    question = Question(
        id=1,
        assignment_id=2,
        question_number=1,
        content="Write about school",
        answer="4",
        max_score=10,
    )
    submission = SimpleNamespace(id=3)

    async def run():
        math_total, math_results = await grade_assignment._grade_math(
            None, submission, [question], "4"
        )
        chinese_total, chinese_results = await grade_assignment._grade_chinese(
            None, submission, [question], "鏄ュぉ鐨勬牎鍥緢缇庛€傛垜寰堝枩娆€"
        )
        english_total, english_results = await grade_assignment._grade_english(
            None, submission, [question], "School is a good place to learn."
        )
        assert len(math_results) == len(chinese_results) == len(english_results) == 1
        assert 0 <= math_total <= 10
        assert 0 <= chinese_total <= 10
        assert 0 <= english_total <= 10

    asyncio.run(run())


def test_run_ocr_uses_cached_text_and_service_fallback(monkeypatch):
    image_cached = SubmissionImage(
        submission_id=1, image_path="cached.png", page_number=1, recognized_text="cached"
    )
    image_remote = SubmissionImage(
        submission_id=1, image_path="remote.png", page_number=2, recognized_text=None
    )

    async def run():
        db = DB([Result(scalars=[image_cached, image_remote])])
        monkeypatch.setattr(
            grade_assignment,
            "read_image_source",
            lambda path: asyncio.sleep(
                0,
                result=SimpleNamespace(
                    content=b"image", content_type="image/png"
                ),
            ),
        )
        async def fake_ocr(data, filename):
            assert filename == "remote.png"
            return {"text": "recognized"}
        monkeypatch.setattr(grade_assignment, "OCR_AVAILABLE", True)
        monkeypatch.setattr(grade_assignment, "ocr_image", fake_ocr)
        text = await grade_assignment._run_ocr_on_images(db, 1)
        assert text == "cached\nrecognized\n"

    asyncio.run(run())


def test_grade_submission_math_updates_mastery_and_report_cache(monkeypatch):
    submission = Submission(id=3, assignment_id=2, student_id=8, status="pending")
    assignment = Assignment(id=2, class_id=4, subject_id=1, teacher_id=5)
    subject = Subject(id=1, name="math")
    question = Question(id=9, assignment_id=2, question_number=1, answer="4", max_score=10)
    db = DB([
        Result(scalar=submission), Result(scalar=assignment), Result(scalar=subject),
        Result(scalars=[question]),
    ])
    calls = {}

    async def fake_mastery(*args, **kwargs):
        calls["mastery"] = True

    async def fake_comment(*args, **kwargs):
        return "comment"

    async def fake_invalidate(*args, **kwargs):
        calls["cache"] = args
        return 1

    monkeypatch.setattr(grade_assignment, "update_mastery_for_results", fake_mastery)
    monkeypatch.setattr(grade_assignment, "generate_comment", fake_comment)
    monkeypatch.setattr(grade_assignment, "invalidate_report_cache", fake_invalidate)
    monkeypatch.setattr(
        grade_assignment, "_run_ocr_on_images", lambda *args: asyncio.sleep(0, result="4")
    )

    asyncio.run(grade_assignment.grade_submission(db, 3))
    assert submission.status == "completed"
    assert float(submission.total_score) == 8.0
    assert submission.comment == "comment"
    assert calls["mastery"] is True
    assert calls["cache"] == (8, 4)
    assert len(db.added) == 1


def test_grade_submission_handles_missing_and_completed_records():
    async def run():
        with pytest.raises(ValueError):
            await grade_assignment.grade_submission(DB([Result()]), 1)

        completed = Submission(id=1, assignment_id=2, student_id=3, status="completed")
        assert await grade_assignment.grade_submission(DB([Result(scalar=completed)]), 1) is None

    asyncio.run(run())


def test_worker_executes_already_completed_submission(monkeypatch):
    submission = Submission(id=3, assignment_id=2, student_id=8, status="completed")
    assignment = Assignment(id=2, class_id=4, subject_id=1, teacher_id=5)
    subject = Subject(id=1, name="math")
    db = DB([
        Result(scalar=submission),
        Result(scalar=assignment),
        Result(scalar=subject),
        Result(scalar=None),
    ])

    class Engine:
        async def dispose(self):
            return None

    class SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(worker, "create_async_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(worker, "async_sessionmaker", lambda *args, **kwargs: lambda: SessionContext())
    published = []
    monkeypatch.setattr(
        worker,
        "publish_submission_status",
        lambda submission_id, status, **kwargs: asyncio.sleep(
            0, result=published.append((submission_id, status))
        ),
    )
    result = asyncio.run(worker._execute_grade_submission(3))
    assert result == {"status": "completed", "submission_id": 3}
    assert published == [(3, "completed")]


def test_worker_retries_unexpected_failures():
    original = worker._execute_grade_submission

    async def fail(submission_id, batch_id=None):
        raise RuntimeError("temporary")

    worker._execute_grade_submission = fail
    try:
        with pytest.raises(Exception):
            worker.grade_submission_task.run(42)
    finally:
        worker._execute_grade_submission = original
