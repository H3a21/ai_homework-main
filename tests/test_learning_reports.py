"""Tests for student and class learning report aggregation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.learning_reports import build_class_report, build_student_report


ROWS = [
    {
        "student_id": 1,
        "knowledge_point_id": 10,
        "knowledge_point_name": "分数加法",
        "subject_id": 1,
        "subject_name": "数学",
        "mastery_level": 0.9,
        "ability_theta": 1.2,
        "attempt_count": 3,
        "success_sum": 2.7,
    },
    {
        "student_id": 1,
        "knowledge_point_id": 11,
        "knowledge_point_name": "分数应用题",
        "subject_id": 1,
        "subject_name": "数学",
        "mastery_level": 0.4,
        "ability_theta": -0.5,
        "attempt_count": 2,
        "success_sum": 0.8,
    },
]


def test_student_report_builds_overview_and_radar():
    report = build_student_report(
        {"id": 1, "name": "学生A"}, ROWS, generated_at="fixed"
    )
    assert report["overview"]["knowledge_point_count"] == 2
    assert report["overview"]["average_mastery"] == 0.65
    assert report["overview"]["average_score_ratio"] == 0.7
    assert len(report["radar"]) == 2


def test_student_report_separates_strengths_and_weak_points():
    report = build_student_report(
        {"id": 1, "name": "学生A"}, ROWS, generated_at="fixed"
    )
    assert report["strengths"][0]["knowledge_point_id"] == 10
    assert report["weak_points"][0]["knowledge_point_id"] == 11
    assert report["weak_points"][0]["is_weak"] is True


def test_student_report_groups_subject_summary():
    report = build_student_report(
        {"id": 1, "name": "学生A"}, ROWS, generated_at="fixed"
    )
    summary = report["subject_summaries"][0]
    assert summary["subject_name"] == "数学"
    assert summary["weak_point_count"] == 1
    assert summary["total_attempts"] == 5


def test_empty_student_report_is_explicit():
    report = build_student_report(
        {"id": 2, "name": "学生B"}, [], generated_at="fixed"
    )
    assert report["overview"]["knowledge_point_count"] == 0
    assert report["radar"] == []
    assert report["weak_points"] == []


def test_class_report_aggregates_students_and_points():
    rows = ROWS + [
        {
            **ROWS[0],
            "student_id": 2,
            "mastery_level": 0.5,
            "attempt_count": 1,
            "success_sum": 0.5,
        }
    ]
    report = build_class_report(
        {"id": 3, "name": "六年级一班"},
        [{"id": 1, "name": "学生A"}, {"id": 2, "name": "学生B"}],
        rows,
        generated_at="fixed",
    )
    assert report["overview"]["student_count"] == 2
    assert report["overview"]["students_with_data"] == 2
    point = next(
        item for item in report["knowledge_points"]
        if item["knowledge_point_id"] == 10
    )
    assert point["average_mastery"] == 0.7
    assert point["weak_student_count"] == 1


def test_class_report_keeps_students_without_mastery_data():
    report = build_class_report(
        {"id": 3, "name": "六年级一班"},
        [{"id": 1, "name": "学生A"}, {"id": 9, "name": "学生C"}],
        ROWS,
        generated_at="fixed",
    )
    empty = next(
        item for item in report["student_summaries"]
        if item["student_id"] == 9
    )
    assert empty["knowledge_point_count"] == 0
    assert empty["average_mastery"] == 0.0


if __name__ == "__main__":
    tests = [
        test_student_report_builds_overview_and_radar,
        test_student_report_separates_strengths_and_weak_points,
        test_student_report_groups_subject_summary,
        test_empty_student_report_is_explicit,
        test_class_report_aggregates_students_and_points,
        test_class_report_keeps_students_without_mastery_data,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
