"""Tests for subject dispatch into concrete grading pipelines."""

import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.grade_assignment import _grade_chinese, _grade_english, resolve_grading_pipeline


def test_subject_names_resolve_without_fixed_database_ids():
    assert resolve_grading_pipeline("数学") == "math"
    assert resolve_grading_pipeline("语文") == "chinese"
    assert resolve_grading_pipeline("英语") == "english"
    assert resolve_grading_pipeline("Chinese") == "chinese"
    assert resolve_grading_pipeline("unknown") == "default"


def test_chinese_dispatch_uses_question_reference_and_caps_score():
    question = SimpleNamespace(
        id=7,
        question_number=1,
        content="请以春天的校园为题写一篇作文",
        answer=None,
        max_score=20.0,
    )
    submission = SimpleNamespace(id=11)
    student_text = (
        "春天的校园充满生机。首先，树木长出了嫩芽；其次，花坛里的花开放了。"
        "最后，同学们在阳光下读书，我喜欢这样的校园。"
    )

    total, results = asyncio.run(
        _grade_chinese(None, submission, [question], student_text)
    )

    assert len(results) == 1
    assert results[0].question_id == 7
    assert results[0].submission_id == 11
    assert 0.0 <= float(results[0].score) <= 20.0
    assert total == float(results[0].score)
    assert "内容相关度" in results[0].feedback
    assert "结构完整度" in results[0].feedback


def test_english_dispatch_uses_question_reference_and_caps_score():
    question = SimpleNamespace(
        id=8,
        question_number=1,
        content="Write about protecting the environment at school",
        answer=None,
        max_score=20.0,
    )
    submission = SimpleNamespace(id=12)
    student_text = (
        "Protecting the environment at school is important. Firstly, students "
        "can save water. Moreover, we can recycle paper and keep classrooms clean."
    )

    total, results = asyncio.run(
        _grade_english(None, submission, [question], student_text)
    )

    assert len(results) == 1
    assert results[0].question_id == 8
    assert results[0].submission_id == 12
    assert 0.0 <= float(results[0].score) <= 20.0
    assert total == float(results[0].score)
    assert "Spelling:" in results[0].feedback
    assert "Content relevance:" in results[0].feedback


if __name__ == "__main__":
    test_subject_names_resolve_without_fixed_database_ids()
    print("PASS: test_subject_names_resolve_without_fixed_database_ids")
    test_chinese_dispatch_uses_question_reference_and_caps_score()
    print("PASS: test_chinese_dispatch_uses_question_reference_and_caps_score")
    test_english_dispatch_uses_question_reference_and_caps_score()
    print("PASS: test_english_dispatch_uses_question_reference_and_caps_score")
