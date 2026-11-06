"""Unit tests for the Celery grading task wrapper."""

import importlib.util
import os
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Keep this unit test runnable in a lightweight host environment. The real
# Celery implementation is verified separately inside the backend container.
if importlib.util.find_spec("celery") is None:
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


def test_worker_task_runs_async_grading_and_returns_completed():
    original = worker._execute_grade_submission

    async def fake_execute(submission_id: int, batch_id: int | None = None) -> dict:
        assert batch_id is None
        return {"status": "completed", "submission_id": submission_id}

    worker._execute_grade_submission = fake_execute
    try:
        result = worker.grade_submission_task.run(42)
    finally:
        worker._execute_grade_submission = original

    assert result == {"status": "completed", "submission_id": 42}


def test_worker_routes_grading_tasks_to_grading_queue():
    assert worker.celery_app.conf.task_routes["grade_submission"]["queue"] == "grading"
    assert worker.celery_app.conf.task_acks_late is True
    assert worker.celery_app.conf.worker_prefetch_multiplier == 1


def test_enqueue_returns_celery_task_id():
    original = worker.grade_submission_task
    calls = []
    worker.grade_submission_task = SimpleNamespace(
        delay=lambda *args: (calls.append(args), SimpleNamespace(id=f"task-{args[0]}"))[1]
    )
    try:
        task_id = worker.enqueue_grade_submission(17)
        batch_task_id = worker.enqueue_grade_submission(18, batch_id=4)
    finally:
        worker.grade_submission_task = original

    assert task_id == "task-17"
    assert batch_task_id == "task-18"
    assert calls == [(17,), (18, 4)]


def test_batch_failure_recording_is_best_effort(monkeypatch):
    async def fail_record(*args):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(worker, "_finish_failed_batch_item", fail_record)
    worker._record_failed_batch_item(4, 17, RuntimeError("grading failed"))


if __name__ == "__main__":
    test_worker_task_runs_async_grading_and_returns_completed()
    print("PASS: test_worker_task_runs_async_grading_and_returns_completed")
    test_worker_routes_grading_tasks_to_grading_queue()
    print("PASS: test_worker_routes_grading_tasks_to_grading_queue")
    test_enqueue_returns_celery_task_id()
    print("PASS: test_enqueue_returns_celery_task_id")
