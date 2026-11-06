"""Tests for deterministic fallback grading comments."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import feedback_engine
from app.feedback_engine import generate_fallback_comment


def test_high_score_comment_is_encouraging_and_subject_specific():
    comment = generate_fallback_comment(
        "英语",
        19.0,
        20.0,
        ["Spelling: good; Grammar: good; No rule-based spelling or grammar errors were found."],
    )
    assert "英语作业" in comment
    assert "完成得很好" in comment
    assert "优势" in comment
    assert "注意拼写" not in comment
    assert "复习相关语法" not in comment


def test_middle_score_comment_includes_detected_issues():
    comment = generate_fallback_comment(
        "语文",
        14.0,
        20.0,
        ["内容相关度较弱；疑似错别字：因该→应该（1处）"],
    )
    assert "语文作业" in comment
    assert "错别字" in comment
    assert "题目要求" in comment
    assert "同类练习" in comment


def test_low_score_math_comment_mentions_process_review():
    comment = generate_fallback_comment("数学", 3.0, 10.0, ["步骤 1 有错误"])
    assert "数学作业" in comment
    assert "错误的步骤" in comment
    assert "订正错题" in comment


def test_correct_math_steps_do_not_trigger_error_suggestions():
    comment = generate_fallback_comment(
        "数学", 10.0, 10.0, ["步骤1正确；答案完全正确"]
    )
    assert "错误的步骤" not in comment
    assert "重新核对" not in comment


def test_comment_is_deterministic_and_has_default_path():
    args = ("unknown", 0.0, 0.0, [])
    first = generate_fallback_comment(*args)
    second = generate_fallback_comment(*args)
    assert first == second
    assert "本次作业" in first
    assert "基础内容" in first


def test_generate_comment_prefers_personalized_llm_result():
    async def fake_llm_comment(subject, total_score, max_score, feedback):
        assert subject == "数学"
        assert total_score == 9.0
        assert list(feedback) == ["步骤正确"]
        return "你已经掌握核心方法，可以继续挑战综合题。"

    original = feedback_engine.generate_llm_comment
    feedback_engine.generate_llm_comment = fake_llm_comment
    try:
        comment = asyncio.run(
            feedback_engine.generate_comment("数学", 9.0, 10.0, ["步骤正确"])
        )
    finally:
        feedback_engine.generate_llm_comment = original
    assert comment == "你已经掌握核心方法，可以继续挑战综合题。"


def test_generate_comment_falls_back_when_llm_is_unavailable():
    async def unavailable(*args, **kwargs):
        return None

    original = feedback_engine.generate_llm_comment
    feedback_engine.generate_llm_comment = unavailable
    try:
        comment = asyncio.run(
            feedback_engine.generate_comment("数学", 3.0, 10.0, ["有错误"])
        )
    finally:
        feedback_engine.generate_llm_comment = original
    assert comment == generate_fallback_comment("数学", 3.0, 10.0, ["有错误"])


if __name__ == "__main__":
    tests = [
        test_high_score_comment_is_encouraging_and_subject_specific,
        test_middle_score_comment_includes_detected_issues,
        test_low_score_math_comment_mentions_process_review,
        test_correct_math_steps_do_not_trigger_error_suggestions,
        test_comment_is_deterministic_and_has_default_path,
        test_generate_comment_prefers_personalized_llm_result,
        test_generate_comment_falls_back_when_llm_is_unavailable,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("\nAll feedback engine tests passed!")
