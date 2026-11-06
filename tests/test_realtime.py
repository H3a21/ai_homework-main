"""Unit tests for authenticated submission WebSocket updates."""

import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace

from fastapi import WebSocketDisconnect

from app.models import Assignment, GradingBatch, Submission
from app.routers import realtime


class FakeResult:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar


class FakeDB:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.rollbacks = 0

    async def execute(self, statement):
        if not self.results:
            raise AssertionError("Unexpected database query")
        return self.results.pop(0)

    async def rollback(self):
        self.rollbacks += 1


class FakeWebSocket:
    def __init__(self, auth_message=None, origin=None):
        self.auth_message = auth_message or {"type": "auth", "token": "token"}
        self.headers = {"origin": origin} if origin else {}
        self.accepted = False
        self.sent = []
        self.close_code = None

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        return self.auth_message

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code):
        self.close_code = code


class FakePubSub:
    def __init__(self, messages):
        self.messages = list(messages)

    async def get_message(self, **kwargs):
        if self.messages:
            return self.messages.pop(0)
        raise WebSocketDisconnect(code=1000)


def _subscription(messages):
    @asynccontextmanager
    async def subscribe(submission_id):
        yield FakePubSub(messages)

    return subscribe


def test_submission_websocket_sends_snapshot_and_status_event(monkeypatch):
    user = SimpleNamespace(id=8, role="student")
    assignment = Assignment(id=2, class_id=1)
    pending = Submission(
        id=4, assignment_id=2, student_id=8, status="grading"
    )
    completed_event = {
        "type": "message",
        "data": json.dumps(
            {
                "type": "submission.status",
                "submission_id": 4,
                "status": "completed",
            }
        ),
    }
    db = FakeDB([
        FakeResult(user),
        FakeResult(pending),
        FakeResult(assignment),
        FakeResult(pending),
    ])
    websocket = FakeWebSocket()
    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 8)
    monkeypatch.setattr(
        realtime,
        "subscribe_submission_events",
        _subscription([completed_event]),
    )

    asyncio.run(realtime.submission_updates(websocket, 4, db))

    assert websocket.accepted is True
    assert websocket.sent == [
        {
            "type": "submission.snapshot",
            "submission_id": 4,
            "status": "grading",
        },
        {
            "type": "submission.status",
            "submission_id": 4,
            "status": "completed",
        },
    ]
    assert db.rollbacks == 1


def test_submission_websocket_rejects_invalid_origin_and_auth(monkeypatch):
    rejected_origin = FakeWebSocket(origin="https://untrusted.example")
    asyncio.run(realtime.submission_updates(rejected_origin, 4, FakeDB()))
    assert rejected_origin.accepted is False
    assert rejected_origin.close_code == 4403

    invalid_auth = FakeWebSocket(auth_message={"type": "not-auth"})
    asyncio.run(realtime.submission_updates(invalid_auth, 4, FakeDB()))
    assert invalid_auth.accepted is True
    assert invalid_auth.close_code == 4401


def test_submission_websocket_enforces_submission_owner(monkeypatch):
    user = SimpleNamespace(id=9, role="student")
    assignment = Assignment(id=2, class_id=1)
    submission = Submission(
        id=4, assignment_id=2, student_id=8, status="grading"
    )
    db = FakeDB([
        FakeResult(user),
        FakeResult(submission),
        FakeResult(assignment),
    ])
    websocket = FakeWebSocket()
    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 9)

    asyncio.run(realtime.submission_updates(websocket, 4, db))

    assert websocket.close_code == 4403
    assert websocket.sent == []
    assert db.rollbacks == 1


def test_completed_submission_websocket_closes_cleanly(monkeypatch):
    user = SimpleNamespace(id=8, role="student")
    assignment = Assignment(id=2, class_id=1)
    submission = Submission(
        id=4, assignment_id=2, student_id=8, status="completed"
    )
    db = FakeDB([
        FakeResult(user),
        FakeResult(submission),
        FakeResult(assignment),
    ])
    websocket = FakeWebSocket()
    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 8)

    asyncio.run(realtime.submission_updates(websocket, 4, db))

    assert websocket.sent[0]["status"] == "completed"
    assert websocket.close_code == 1000
    assert db.rollbacks == 1


def test_batch_websocket_sends_progress_and_closes_at_terminal_event(monkeypatch):
    user = SimpleNamespace(id=5, role="teacher")
    assignment = Assignment(id=2, class_id=1)
    batch = GradingBatch(
        id=6,
        assignment_id=2,
        teacher_id=5,
        total_submissions=2,
        completed_submissions=0,
        failed_submissions=0,
        status="grading",
    )
    event = {
        "type": "message",
        "data": json.dumps({
            "type": "grading_batch.status",
            "batch_id": 6,
            "status": "completed",
            "total_submissions": 2,
            "completed_submissions": 2,
            "failed_submissions": 0,
            "finished_submissions": 2,
            "progress_percent": 100.0,
        }),
    }
    db = FakeDB([
        FakeResult(user),
        FakeResult(batch),
        FakeResult(assignment),
        FakeResult(batch),
    ])
    websocket = FakeWebSocket()

    async def allow(*args):
        return None

    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 5)
    monkeypatch.setattr(realtime, "require_class_teacher", allow)
    monkeypatch.setattr(realtime, "subscribe_batch_events", _subscription([event]))

    asyncio.run(realtime.grading_batch_updates(websocket, 6, db))

    assert websocket.sent[0]["type"] == "grading_batch.snapshot"
    assert websocket.sent[0]["progress_percent"] == 0.0
    assert websocket.sent[1]["status"] == "completed"
    assert websocket.close_code == 1000


def test_batch_websocket_rejects_invalid_scope_and_missing_resources(monkeypatch):
    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 5)

    async def run():
        invalid_origin = FakeWebSocket(origin="https://untrusted.example")
        await realtime.grading_batch_updates(invalid_origin, 6, FakeDB())
        assert invalid_origin.close_code == 4403
        assert invalid_origin.accepted is False

        student_socket = FakeWebSocket()
        await realtime.grading_batch_updates(
            student_socket,
            6,
            FakeDB([FakeResult(SimpleNamespace(id=5, role="student"))]),
        )
        assert student_socket.close_code == 4403

        missing_batch = FakeWebSocket()
        await realtime.grading_batch_updates(
            missing_batch,
            6,
            FakeDB([
                FakeResult(SimpleNamespace(id=5, role="teacher")),
                FakeResult(),
            ]),
        )
        assert missing_batch.close_code == 4404

        batch = GradingBatch(id=6, assignment_id=2, status="grading")
        missing_assignment = FakeWebSocket()
        await realtime.grading_batch_updates(
            missing_assignment,
            6,
            FakeDB([
                FakeResult(SimpleNamespace(id=5, role="teacher")),
                FakeResult(batch),
                FakeResult(),
            ]),
        )
        assert missing_assignment.close_code == 4404

    asyncio.run(run())


def test_terminal_batch_websocket_sends_snapshot_and_closes(monkeypatch):
    user = SimpleNamespace(id=5, role="teacher")
    assignment = Assignment(id=2, class_id=1)
    batch = GradingBatch(
        id=6,
        assignment_id=2,
        teacher_id=5,
        total_submissions=2,
        completed_submissions=1,
        failed_submissions=1,
        status="failed",
    )
    websocket = FakeWebSocket()

    async def allow(*args):
        return None

    monkeypatch.setattr(realtime, "decode_access_token", lambda token: 5)
    monkeypatch.setattr(realtime, "require_class_teacher", allow)
    asyncio.run(
        realtime.grading_batch_updates(
            websocket,
            6,
            FakeDB([FakeResult(user), FakeResult(batch), FakeResult(assignment)]),
        )
    )

    assert websocket.sent[0]["status"] == "failed"
    assert websocket.sent[0]["progress_percent"] == 100.0
    assert websocket.close_code == 1000
