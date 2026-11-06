"""Unit tests for Prometheus metrics and structured observability hooks."""

import asyncio
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from prometheus_client import REGISTRY, generate_latest

from app.observability import JsonFormatter, observe_http_request


class FakeRequest:
    method = "GET"
    headers = {}
    scope = {"route": SimpleNamespace(path="/api/test")}
    url = SimpleNamespace(path="/api/test")
    client = SimpleNamespace(host="127.0.0.1")
    state = SimpleNamespace()


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.headers = {}


def test_metrics_exposition_contains_application_metrics():
    payload = generate_latest(REGISTRY).decode("utf-8")

    assert "ai_homework_http_requests_total" in payload
    assert "ai_homework_http_request_duration_seconds" in payload
    assert "ai_homework_grading_tasks_total" in payload
    assert "ai_homework_grading_duration_seconds" in payload


def test_http_middleware_adds_request_id_and_records_route():
    async def call_next(request):
        return FakeResponse(204)

    response = asyncio.run(observe_http_request(FakeRequest(), call_next))
    assert response.headers["X-Request-ID"]

    payload = generate_latest(REGISTRY).decode("utf-8")
    assert 'route="/api/test"' in payload
    assert 'status="204"' in payload


def test_json_formatter_emits_structured_fields():
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="grading_attempt_completed",
        args=(),
        exc_info=None,
    )
    record.submission_id = 42
    record.task_status = "completed"
    record.duration_ms = 12.5

    payload = json.loads(JsonFormatter("test-service").format(record))
    assert payload["service"] == "test-service"
    assert payload["message"] == "grading_attempt_completed"
    assert payload["submission_id"] == 42
    assert payload["task_status"] == "completed"
    assert payload["duration_ms"] == 12.5


def test_security_audit_records_mutating_actor(caplog):
    from app.observability import _audit_http_request

    request = FakeRequest()
    request.method = "POST"
    request.state = SimpleNamespace(actor_id=7)
    with caplog.at_level("INFO", logger="app.audit"):
        _audit_http_request(request, 201, "request-1")

    record = caplog.records[-1]
    assert record.event == "data_change"
    assert record.action == "test.create"
    assert record.outcome == "success"
    assert record.actor_id == 7
    assert record.client_id != "127.0.0.1"
    assert len(record.client_id) == 16


def test_http_middleware_persists_mutating_audit(monkeypatch):
    import app.observability as observability

    captured = []

    async def persist(event):
        captured.append(event)
        return True

    async def call_next(request):
        request.state.actor_id = 7
        return FakeResponse(201)

    request = FakeRequest()
    request.method = "POST"
    request.state = SimpleNamespace()
    monkeypatch.setattr(observability, "persist_audit_event", persist)

    asyncio.run(observability.observe_http_request(request, call_next))

    assert len(captured) == 1
    assert captured[0].action == "test.create"
    assert captured[0].user_id == 7
    assert captured[0].outcome == "success"


def test_grading_attempt_records_worker_metric():
    try:
        import celery  # noqa: F401
    except ModuleNotFoundError:
        import types

        fake_celery = types.ModuleType("celery")

        class FakeTask:
            def __init__(self, function, bind):
                self.function = function
                self.bind = bind

            def run(self, *args, **kwargs):
                if self.bind:
                    return self.function(self, *args, **kwargs)
                return self.function(*args, **kwargs)

            def delay(self, *args, **kwargs):
                return SimpleNamespace(id="test-task-id")

        class FakeCelery:
            def __init__(self, *args, **kwargs):
                self.conf = SimpleNamespace()

            def task(self, bind=False, **kwargs):
                def decorator(function):
                    return FakeTask(function, bind)

                return decorator

        fake_celery.Celery = FakeCelery
        sys.modules["celery"] = fake_celery

    import app.worker as worker
    worker._record_grading_attempt(42, "math", "completed", 0.25)

    payload = generate_latest(REGISTRY).decode("utf-8")
    assert any(
        "ai_homework_grading_tasks_total" in line
        and 'status="completed"' in line
        and 'subject="' in line
        for line in payload.splitlines()
    )


if __name__ == "__main__":
    test_metrics_exposition_contains_application_metrics()
    print("PASS: test_metrics_exposition_contains_application_metrics")
    test_http_middleware_adds_request_id_and_records_route()
    print("PASS: test_http_middleware_adds_request_id_and_records_route")
    test_json_formatter_emits_structured_fields()
    print("PASS: test_json_formatter_emits_structured_fields")
    test_grading_attempt_records_worker_metric()
    print("PASS: test_grading_attempt_records_worker_metric")
