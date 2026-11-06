"""Aggregations for student and class learning reports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


WEAK_MASTERY_THRESHOLD = 0.60
STRONG_MASTERY_THRESHOLD = 0.80


def _rounded(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _overview(rows: Sequence[dict]) -> dict:
    point_count = len(rows)
    total_attempts = sum(int(row.get("attempt_count", 0)) for row in rows)
    success_sum = sum(float(row.get("success_sum", 0.0)) for row in rows)
    average_mastery = (
        sum(float(row.get("mastery_level", 0.0)) for row in rows) / point_count
        if point_count else 0.0
    )
    weak_count = sum(
        float(row.get("mastery_level", 0.0)) < WEAK_MASTERY_THRESHOLD
        for row in rows
    )
    return {
        "knowledge_point_count": point_count,
        "average_mastery": _rounded(average_mastery),
        "weak_point_count": weak_count,
        "total_attempts": total_attempts,
        "average_score_ratio": _rounded(success_sum / total_attempts)
        if total_attempts else 0.0,
    }


def _point_payload(row: dict) -> dict:
    mastery_level = float(row.get("mastery_level", 0.0))
    return {
        "knowledge_point_id": int(row["knowledge_point_id"]),
        "knowledge_point_name": str(row["knowledge_point_name"]),
        "subject_id": int(row["subject_id"]),
        "subject_name": str(row["subject_name"]),
        "mastery_level": _rounded(mastery_level),
        "ability_theta": _rounded(float(row.get("ability_theta", 0.0))),
        "attempt_count": int(row.get("attempt_count", 0)),
        "average_score_ratio": _rounded(
            float(row.get("success_sum", 0.0)) / int(row.get("attempt_count", 0))
        ) if int(row.get("attempt_count", 0)) else 0.0,
        "is_weak": mastery_level < WEAK_MASTERY_THRESHOLD,
    }


def build_student_report(
    student: dict,
    mastery_rows: Sequence[dict],
    subject_id: int | None = None,
    generated_at: str | None = None,
) -> dict:
    points = [_point_payload(row) for row in mastery_rows]
    points.sort(key=lambda item: (item["subject_id"], item["knowledge_point_id"]))

    subjects: dict[int, list[dict]] = {}
    for point in points:
        subjects.setdefault(point["subject_id"], []).append(point)

    subject_summaries = []
    for current_subject_id, subject_points in subjects.items():
        subject_summaries.append({
            "subject_id": current_subject_id,
            "subject_name": subject_points[0]["subject_name"],
            "knowledge_point_count": len(subject_points),
            "average_mastery": _rounded(
                sum(point["mastery_level"] for point in subject_points)
                / len(subject_points)
            ),
            "weak_point_count": sum(point["is_weak"] for point in subject_points),
            "total_attempts": sum(point["attempt_count"] for point in subject_points),
        })

    weak_points = sorted(
        (point for point in points if point["is_weak"]),
        key=lambda point: (point["mastery_level"], -point["attempt_count"]),
    )
    strengths = sorted(
        (
            point for point in points
            if point["mastery_level"] >= STRONG_MASTERY_THRESHOLD
        ),
        key=lambda point: (-point["mastery_level"], -point["attempt_count"]),
    )

    return {
        "report_type": "student",
        "student_id": int(student["id"]),
        "student_name": str(student["name"]),
        "subject_id": subject_id,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "overview": _overview(mastery_rows),
        "subject_summaries": subject_summaries,
        "radar": points,
        "weak_points": weak_points[:5],
        "strengths": strengths[:5],
    }


def build_class_report(
    class_info: dict,
    students: Sequence[dict],
    mastery_rows: Sequence[dict],
    subject_id: int | None = None,
    generated_at: str | None = None,
) -> dict:
    rows_by_student: dict[int, list[dict]] = {}
    rows_by_point: dict[int, list[dict]] = {}
    for row in mastery_rows:
        rows_by_student.setdefault(int(row["student_id"]), []).append(row)
        rows_by_point.setdefault(int(row["knowledge_point_id"]), []).append(row)

    student_summaries = []
    for student in students:
        rows = rows_by_student.get(int(student["id"]), [])
        summary = _overview(rows)
        student_summaries.append({
            "student_id": int(student["id"]),
            "student_name": str(student["name"]),
            **summary,
        })
    student_summaries.sort(
        key=lambda item: (item["average_mastery"], item["student_id"])
    )

    knowledge_points = []
    for knowledge_point_id, rows in rows_by_point.items():
        mastery_values = [float(row.get("mastery_level", 0.0)) for row in rows]
        weak_students = sum(
            mastery < WEAK_MASTERY_THRESHOLD for mastery in mastery_values
        )
        knowledge_points.append({
            "knowledge_point_id": knowledge_point_id,
            "knowledge_point_name": str(rows[0]["knowledge_point_name"]),
            "subject_id": int(rows[0]["subject_id"]),
            "subject_name": str(rows[0]["subject_name"]),
            "average_mastery": _rounded(
                sum(mastery_values) / len(mastery_values)
            ),
            "covered_student_count": len(rows),
            "weak_student_count": weak_students,
            "weak_rate": _rounded(weak_students / len(rows)),
            "total_attempts": sum(int(row.get("attempt_count", 0)) for row in rows),
        })
    knowledge_points.sort(
        key=lambda item: (item["average_mastery"], item["knowledge_point_id"])
    )

    overview = _overview(mastery_rows)
    overview.update({
        "student_count": len(students),
        "students_with_data": len(rows_by_student),
    })

    return {
        "report_type": "class",
        "class_id": int(class_info["id"]),
        "class_name": str(class_info["name"]),
        "subject_id": subject_id,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "overview": overview,
        "knowledge_points": knowledge_points,
        "weak_knowledge_points": [
            point for point in knowledge_points if point["weak_student_count"] > 0
        ][:5],
        "student_summaries": student_summaries,
    }


def _normalize_mastery_row(mastery, point, subject, student=None) -> dict:
    row = {
        "knowledge_point_id": point.id,
        "knowledge_point_name": point.name,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "mastery_level": float(mastery.mastery_level or 0.0),
        "ability_theta": float(mastery.ability_theta or 0.0),
        "attempt_count": int(mastery.attempt_count or 0),
        "success_sum": float(mastery.success_sum or 0.0),
    }
    if student is not None:
        row.update({"student_id": student.id, "student_name": student.display_name})
    return row


async def load_student_report(
    db: "AsyncSession",
    student_id: int,
    subject_id: int | None = None,
) -> dict | None:
    from app.models import KnowledgePoint, StudentKnowledgeMastery, Subject, User

    student = (
        await db.execute(select(User).where(User.id == student_id, User.role == "student"))
    ).scalar_one_or_none()
    if not student:
        return None

    query = (
        select(StudentKnowledgeMastery, KnowledgePoint, Subject)
        .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeMastery.knowledge_point_id)
        .join(Subject, Subject.id == KnowledgePoint.subject_id)
        .where(StudentKnowledgeMastery.student_id == student_id)
    )
    if subject_id:
        query = query.where(KnowledgePoint.subject_id == subject_id)
    rows = (await db.execute(query)).all()
    normalized = [
        _normalize_mastery_row(mastery, point, subject)
        for mastery, point, subject in rows
    ]
    return build_student_report(
        {"id": student.id, "name": student.display_name},
        normalized,
        subject_id,
    )


async def load_class_report(
    db: "AsyncSession",
    class_id: int,
    subject_id: int | None = None,
) -> dict | None:
    from app.models import (
        Class,
        ClassMember,
        KnowledgePoint,
        StudentKnowledgeMastery,
        Subject,
        User,
    )

    classroom = (
        await db.execute(select(Class).where(Class.id == class_id))
    ).scalar_one_or_none()
    if not classroom:
        return None

    student_rows = (
        await db.execute(
            select(User)
            .join(ClassMember, ClassMember.user_id == User.id)
            .where(ClassMember.class_id == class_id, ClassMember.role == "student")
            .order_by(User.display_name, User.id)
        )
    ).scalars().all()
    student_ids = [student.id for student in student_rows]

    normalized = []
    if student_ids:
        query = (
            select(StudentKnowledgeMastery, KnowledgePoint, Subject, User)
            .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeMastery.knowledge_point_id)
            .join(Subject, Subject.id == KnowledgePoint.subject_id)
            .join(User, User.id == StudentKnowledgeMastery.student_id)
            .where(StudentKnowledgeMastery.student_id.in_(student_ids))
        )
        if subject_id:
            query = query.where(KnowledgePoint.subject_id == subject_id)
        rows = (await db.execute(query)).all()
        normalized = [
            _normalize_mastery_row(mastery, point, subject, student)
            for mastery, point, subject, student in rows
        ]

    return build_class_report(
        {"id": classroom.id, "name": classroom.name},
        [{"id": student.id, "name": student.display_name} for student in student_rows],
        normalized,
        subject_id,
    )
