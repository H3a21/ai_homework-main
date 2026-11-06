"""Schema contract tests for audit logs and grading history."""

from app.models import AuditLog, GradingAttempt, GradingBatch, GradingBatchItem


def test_grading_batch_tracks_summary_and_item_contract():
    batch_columns = GradingBatch.__table__.columns
    for name in (
        "assignment_id",
        "teacher_id",
        "total_submissions",
        "completed_submissions",
        "failed_submissions",
        "status",
        "error_message",
        "completed_at",
    ):
        assert name in batch_columns
    assert batch_columns["assignment_id"].nullable is False
    assert batch_columns["teacher_id"].nullable is False
    assert batch_columns["status"].nullable is False

    item_columns = GradingBatchItem.__table__.columns
    for name in ("batch_id", "submission_id", "task_id", "status", "error_message"):
        assert name in item_columns
    constraints = {
        constraint.name for constraint in GradingBatchItem.__table__.constraints
    }
    assert "uk_grading_batch_item" in constraints


def test_grading_attempt_has_version_and_snapshot_contract():
    columns = GradingAttempt.__table__.columns
    assert columns["submission_id"].nullable is False
    assert columns["attempt_number"].nullable is False
    assert columns["status"].nullable is False
    assert columns["raw_ocr_result"].type.python_type is dict
    assert columns["result_snapshot"].type.python_type is dict

    constraints = {
        constraint.name for constraint in GradingAttempt.__table__.constraints
    }
    assert "uk_submission_attempt" in constraints


def test_audit_log_has_trace_actor_resource_and_snapshot_contract():
    columns = AuditLog.__table__.columns
    for name in (
        "request_id",
        "user_id",
        "action",
        "resource_type",
        "resource_id",
        "old_value",
        "new_value",
        "ip_address",
        "user_agent",
        "outcome",
        "method",
        "path",
        "status_code",
    ):
        assert name in columns
    assert columns["request_id"].nullable is False
    assert columns["user_id"].nullable is True
    assert columns["old_value"].type.python_type is dict
