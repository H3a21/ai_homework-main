"""Tests for the deterministic English grading pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.english_pipeline import (
    analyze_english_answer,
    detect_grammar_errors,
    detect_spelling_errors,
    grade_english_answer,
)


def test_detects_common_spelling_errors():
    findings = detect_spelling_errors(
        "I beleive my freind can acheive success becuase she works hard."
    )
    corrections = {item.original: item.suggestion for item in findings}
    assert corrections["beleive"] == "believe"
    assert corrections["freind"] == "friend"
    assert corrections["acheive"] == "achieve"
    assert corrections["becuase"] == "because"


def test_detects_subject_verb_and_article_errors():
    findings = detect_grammar_errors("he go to a interesting school. They is kind")
    codes = {item.code for item in findings}
    assert "sentence-capitalization" in codes
    assert "third-person-singular" in codes
    assert "subject-verb-agreement" in codes
    assert "article-a-an" in codes
    assert "terminal-punctuation" in codes


def test_empty_answer_scores_zero():
    score, feedback = grade_english_answer("", "Write about school life", 20.0)
    assert score == 0.0
    assert "No English answer" in feedback


def test_relevant_writing_scores_above_unrelated_writing():
    prompt = "Write an essay about protecting the environment at school"
    relevant = (
        "Protecting the environment at school is important. Firstly, students can "
        "save water and electricity. Moreover, we can recycle paper and keep the "
        "classroom clean. Therefore, every student can make our school greener."
    )
    unrelated = (
        "My favorite sport is basketball. I practice with my friends after class. "
        "The game is exciting and our team works together every day."
    )
    relevant_analysis = analyze_english_answer(relevant, prompt)
    unrelated_analysis = analyze_english_answer(unrelated, prompt)
    assert relevant_analysis.relevance_score > unrelated_analysis.relevance_score
    assert relevant_analysis.score_ratio > unrelated_analysis.score_ratio


def test_vocabulary_rewards_varied_connected_writing():
    repetitive = "School is good. School is good. School is good."
    varied = (
        "Although school life can be busy, collaborative projects develop creativity. "
        "Moreover, thoughtful discussions encourage students to communicate clearly."
    )
    repetitive_analysis = analyze_english_answer(repetitive, "school life")
    varied_analysis = analyze_english_answer(varied, "school life")
    assert varied_analysis.vocabulary_score > repetitive_analysis.vocabulary_score


def test_feedback_exposes_dimensions_and_corrections():
    analysis = analyze_english_answer(
        "he beleive exercise are important for health",
        "Write about exercise and health",
    )
    assert "Spelling:" in analysis.feedback
    assert "Grammar:" in analysis.feedback
    assert "Vocabulary:" in analysis.feedback
    assert "Content relevance:" in analysis.feedback
    assert "beleive->believe" in analysis.feedback


def test_score_is_deterministic_and_bounded():
    text = "Exercise keeps us healthy. Therefore, I walk to school every day."
    first = grade_english_answer(text, "exercise and health", 15.0)
    second = grade_english_answer(text, "exercise and health", 15.0)
    assert first == second
    assert 0.0 <= first[0] <= 15.0


if __name__ == "__main__":
    tests = [
        test_detects_common_spelling_errors,
        test_detects_subject_verb_and_article_errors,
        test_empty_answer_scores_zero,
        test_relevant_writing_scores_above_unrelated_writing,
        test_vocabulary_rewards_varied_connected_writing,
        test_feedback_exposes_dimensions_and_corrections,
        test_score_is_deterministic_and_bounded,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("\nAll English pipeline tests passed!")
