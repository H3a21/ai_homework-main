"""Tests for append-only audit event persistence."""

import asyncio

from app import audit_service


class FakeSession:
    def __init__(self, fail=False):
        self.fail = fail
        self.added = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        if self.fail:
            raise RuntimeError("database unavailable")
        self.commits += 1


def _event() -> audit_service.AuditEvent:
    return audit_service.AuditEvent(
        request_id="00000000-0000-0000-0000-000000000001",
        user_id=7,
        action="submission.grade",
        resource_type="submission",
        resource_id=42,
        old_value={"status": "pending"},
        new_value={"status": "grading"},
        ip_address="127.0.0.1",
        user_agent="pytest",
        outcome="success",
        method="POST",
        path="/api/submissions/42/grade",
        status_code=202,
    )


def test_persist_audit_event_inserts_once(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(audit_service, "AsyncSession", lambda: session)

    assert asyncio.run(audit_service.persist_audit_event(_event())) is True
    assert session.commits == 1
    assert len(session.added) == 1
    record = session.added[0]
    assert record.action == "submission.grade"
    assert record.old_value == {"status": "pending"}
    assert record.new_value == {"status": "grading"}


def test_persist_audit_event_failure_does_not_escape(monkeypatch):
    session = FakeSession(fail=True)
    monkeypatch.setattr(audit_service, "AsyncSession", lambda: session)

    assert asyncio.run(audit_service.persist_audit_event(_event())) is False
