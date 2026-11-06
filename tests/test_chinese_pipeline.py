"""Tests for the deterministic Chinese grading pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.chinese_pipeline import (
    analyze_chinese_answer,
    detect_typos,
    grade_chinese_answer,
)


def test_detects_conservative_phrase_typos():
    findings = detect_typos("我们因该认真学习，以经制定了计划。")
    corrections = {item.original: item.suggestion for item in findings}
    assert corrections["因该"] == "应该"
    assert corrections["以经"] == "已经"


def test_detects_unusual_repeated_characters():
    findings = detect_typos("这次作业我我我一定认真完成。")
    assert any(item.original == "我我我" and item.suggestion == "我" for item in findings)


def test_empty_answer_scores_zero():
    score, feedback = grade_chinese_answer("", "请以春天为题写一篇作文", 20.0)
    assert score == 0.0
    assert "未检测到" in feedback


def test_relevant_composition_scores_above_unrelated_text():
    prompt = "请以春天的校园为题写一篇作文"
    relevant = (
        "春天的校园充满生机。首先，操场边的小树长出了嫩芽；"
        "其次，花坛里的花慢慢开放。最后，同学们在温暖的阳光下读书，"
        "我喜欢春天的校园。"
    )
    unrelated = (
        "我最喜欢制作模型。首先准备零件，然后阅读说明书，最后完成组装。"
        "整个过程需要耐心，也让我学会了认真检查。"
    )

    relevant_analysis = analyze_chinese_answer(relevant, prompt)
    unrelated_analysis = analyze_chinese_answer(unrelated, prompt)

    assert relevant_analysis.relevance_score > unrelated_analysis.relevance_score
    assert relevant_analysis.score_ratio > unrelated_analysis.score_ratio


def test_structure_rewards_complete_multi_sentence_writing():
    short_text = "春天真美。"
    complete_text = (
        "春天来了，校园里的树木长出了嫩芽。首先，我看见花坛里开满鲜花。\n"
        "其次，同学们在操场上快乐地运动。最后，我想把这份美好记录下来。"
    )

    short_analysis = analyze_chinese_answer(short_text, "春天的校园")
    complete_analysis = analyze_chinese_answer(complete_text, "春天的校园")

    assert complete_analysis.structure_score > short_analysis.structure_score
    assert complete_analysis.score_ratio > short_analysis.score_ratio


def test_feedback_exposes_scoring_dimensions_and_typos():
    analysis = analyze_chinese_answer(
        "我因该认真观察春天。首先记录花草，然后写下感受。",
        "观察春天并写下感受",
    )
    assert "内容相关度" in analysis.feedback
    assert "句子通顺度" in analysis.feedback
    assert "结构完整度" in analysis.feedback
    assert "因该→应该" in analysis.feedback


def test_score_is_deterministic_and_bounded():
    text = "因为春天很温暖，所以我喜欢在校园里散步。"
    first = grade_chinese_answer(text, "春天的校园", 15.0)
    second = grade_chinese_answer(text, "春天的校园", 15.0)
    assert first == second
    assert 0.0 <= first[0] <= 15.0


if __name__ == "__main__":
    tests = [
        test_detects_conservative_phrase_typos,
        test_detects_unusual_repeated_characters,
        test_empty_answer_scores_zero,
        test_relevant_composition_scores_above_unrelated_text,
        test_structure_rewards_complete_multi_sentence_writing,
        test_feedback_exposes_scoring_dimensions_and_typos,
        test_score_is_deterministic_and_bounded,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("\nAll Chinese pipeline tests passed!")
