"""Knowledge-point mastery updates using a bounded online 2PL-IRT step."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models import GradingResult, Question, StudentKnowledgeMastery


THETA_MIN = -3.0
THETA_MAX = 3.0
DEFAULT_THETA = 0.0
DEFAULT_DISCRIMINATION = 1.0
DEFAULT_LEARNING_RATE = 1.0


@dataclass(frozen=True)
class IRTUpdate:
    score_ratio: float
    expected_probability: float
    ability_theta: float
    mastery_level: float


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def sigmoid(value: float) -> float:
    if value >= 0:
        exponential = math.exp(-value)
        return 1.0 / (1.0 + exponential)
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def normalize_score(score: float | None, max_score: float | None) -> float:
    if score is None or max_score is None or max_score <= 0:
        return 0.0
    return clamp(float(score) / float(max_score), 0.0, 1.0)


def calculate_irt_update(
    theta: float,
    score_ratio: float,
    difficulty: float = 0.0,
    discrimination: float = DEFAULT_DISCRIMINATION,
    learning_rate: float = DEFAULT_LEARNING_RATE,
) -> IRTUpdate:
    """Apply one 2PL-IRT gradient step, treating partial credit as soft truth."""
    bounded_theta = clamp(float(theta), THETA_MIN, THETA_MAX)
    bounded_ratio = clamp(float(score_ratio), 0.0, 1.0)
    bounded_difficulty = float(difficulty)
    bounded_discrimination = max(float(discrimination), 0.1)
    bounded_learning_rate = max(float(learning_rate), 0.0)

    expected = sigmoid(
        bounded_discrimination * (bounded_theta - bounded_difficulty)
    )
    next_theta = clamp(
        bounded_theta
        + bounded_learning_rate
        * bounded_discrimination
        * (bounded_ratio - expected),
        THETA_MIN,
        THETA_MAX,
    )
    return IRTUpdate(
        score_ratio=bounded_ratio,
        expected_probability=expected,
        ability_theta=next_theta,
        mastery_level=sigmoid(next_theta),
    )


def apply_irt_observation(
    record: StudentKnowledgeMastery,
    score_ratio: float,
    difficulty: float,
    discrimination: float,
) -> IRTUpdate:
    update = calculate_irt_update(
        float(record.ability_theta or DEFAULT_THETA),
        score_ratio,
        difficulty,
        discrimination,
    )
    record.ability_theta = round(update.ability_theta, 3)
    record.mastery_level = round(update.mastery_level, 2)
    record.attempt_count = int(record.attempt_count or 0) + 1
    record.success_sum = round(
        float(record.success_sum or 0.0) + update.score_ratio,
        3,
    )
    return update


async def update_mastery_for_results(
    db: AsyncSession,
    student_id: int,
    questions_by_id: Mapping[int, Question],
    grading_results: Sequence[GradingResult],
) -> int:
    """Persist one mastery record per knowledge point touched by a submission."""
    from app.models import StudentKnowledgeMastery

    updated_points: set[int] = set()
    observations: dict[int, list[tuple[float, float, float]]] = {}
    for result in grading_results:
        question = questions_by_id.get(result.question_id)
        if not question or not question.knowledge_point_id:
            continue
        score_ratio = normalize_score(result.score, question.max_score)
        observations.setdefault(question.knowledge_point_id, []).append(
            (
                score_ratio,
                float(question.difficulty or 0.0),
                float(question.discrimination or DEFAULT_DISCRIMINATION),
            )
        )

    for knowledge_point_id, point_observations in observations.items():
        result = await db.execute(
            select(StudentKnowledgeMastery).where(
                StudentKnowledgeMastery.student_id == student_id,
                StudentKnowledgeMastery.knowledge_point_id == knowledge_point_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            record = StudentKnowledgeMastery(
                student_id=student_id,
                knowledge_point_id=knowledge_point_id,
                mastery_level=0.50,
                ability_theta=DEFAULT_THETA,
                attempt_count=0,
                success_sum=0.0,
            )
            db.add(record)
            await db.flush()

        for score_ratio, difficulty, discrimination in point_observations:
            apply_irt_observation(record, score_ratio, difficulty, discrimination)
        updated_points.add(knowledge_point_id)

    return len(updated_points)
