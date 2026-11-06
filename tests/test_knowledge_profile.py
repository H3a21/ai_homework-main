"""Tests for bounded online IRT mastery updates."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.knowledge_profile import (
    THETA_MAX,
    THETA_MIN,
    calculate_irt_update,
    normalize_score,
    sigmoid,
)


def test_sigmoid_and_score_normalization_are_bounded():
    assert sigmoid(-100) < 0.01
    assert sigmoid(100) > 0.99
    assert normalize_score(15, 10) == 1.0
    assert normalize_score(-1, 10) == 0.0
    assert normalize_score(None, 10) == 0.0


def test_high_score_increases_theta_and_mastery():
    update = calculate_irt_update(0.0, 1.0)
    assert update.ability_theta > 0.0
    assert update.mastery_level > 0.5
    assert update.expected_probability == 0.5


def test_low_score_decreases_theta_and_mastery():
    update = calculate_irt_update(0.0, 0.0)
    assert update.ability_theta < 0.0
    assert update.mastery_level < 0.5


def test_partial_score_produces_a_bounded_intermediate_update():
    update = calculate_irt_update(0.0, 0.5)
    assert update.ability_theta == 0.0
    assert update.mastery_level == 0.5
    assert THETA_MIN <= update.ability_theta <= THETA_MAX


def test_harder_item_has_lower_expected_probability():
    easy = calculate_irt_update(0.0, 0.5, difficulty=-1.0)
    hard = calculate_irt_update(0.0, 0.5, difficulty=1.0)
    assert easy.expected_probability > hard.expected_probability
    assert easy.ability_theta < hard.ability_theta


def test_repeated_perfect_scores_converge_without_exceeding_bounds():
    theta = 0.0
    for _ in range(30):
        theta = calculate_irt_update(theta, 1.0).ability_theta
    assert 0.0 < theta <= THETA_MAX
    assert calculate_irt_update(THETA_MAX, 1.0).ability_theta == THETA_MAX


if __name__ == "__main__":
    tests = [
        test_sigmoid_and_score_normalization_are_bounded,
        test_high_score_increases_theta_and_mastery,
        test_low_score_decreases_theta_and_mastery,
        test_partial_score_produces_a_bounded_intermediate_update,
        test_harder_item_has_lower_expected_probability,
        test_repeated_perfect_scores_converge_without_exceeding_bounds,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
