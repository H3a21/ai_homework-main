"""Unit tests for Redis-backed submission status events."""

import asyncio
import json

from app import submission_events


class FakePubSub:
    def __init__(self):
        self.subscribed = []
        self.unsubscribed = []
        self.closed = False

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed.append(channel)

    async def aclose(self):
        self.closed = True


class FakeRedis:
    def __init__(self):
        self.published = []
        self.closed = False
        self.subscription = FakePubSub()

    async def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    def pubsub(self):
        return self.subscription

    async def aclose(self):
        self.closed = True


def test_publish_submission_status_serializes_expected_event(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(submission_events, "_redis_client", lambda: client)

    async def run():
        assert await submission_events.publish_submission_status(
            42, "pending", reason="retrying"
        ) is True
        channel, raw_payload = client.published[0]
        payload = json.loads(raw_payload)
        assert channel == "submission-events:42"
        assert payload["type"] == "submission.status"
        assert payload["submission_id"] == 42
        assert payload["status"] == "pending"
        assert payload["reason"] == "retrying"
        assert payload["timestamp"]
        assert client.closed is True

    asyncio.run(run())


def test_publish_batch_status_includes_aggregate_progress(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(submission_events, "_redis_client", lambda: client)

    async def run():
        assert await submission_events.publish_batch_status(
            5,
            "grading",
            total_submissions=4,
            completed_submissions=2,
            failed_submissions=1,
        ) is True
        channel, raw_payload = client.published[0]
        payload = json.loads(raw_payload)
        assert channel == "grading-batch-events:5"
        assert payload["type"] == "grading_batch.status"
        assert payload["finished_submissions"] == 3
        assert payload["progress_percent"] == 75.0

    asyncio.run(run())


def test_subscription_releases_pubsub_and_client(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(submission_events, "_redis_client", lambda: client)

    async def run():
        async with submission_events.subscribe_submission_events(7) as pubsub:
            assert pubsub is client.subscription
            assert pubsub.subscribed == ["submission-events:7"]

        assert client.subscription.unsubscribed == ["submission-events:7"]
        assert client.subscription.closed is True
        assert client.closed is True

    asyncio.run(run())


def test_batch_subscription_releases_pubsub_and_client(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(submission_events, "_redis_client", lambda: client)

    async def run():
        async with submission_events.subscribe_batch_events(5) as pubsub:
            assert pubsub is client.subscription
            assert pubsub.subscribed == ["grading-batch-events:5"]
        assert client.subscription.unsubscribed == ["grading-batch-events:5"]
        assert client.subscription.closed is True
        assert client.closed is True

    asyncio.run(run())


def test_publish_failure_is_best_effort(monkeypatch):
    client = FakeRedis()

    async def fail_publish(channel, payload):
        raise ConnectionError("redis unavailable")

    client.publish = fail_publish
    monkeypatch.setattr(submission_events, "_redis_client", lambda: client)

    async def run():
        assert await submission_events.publish_submission_status(
            9, "grading"
        ) is False
        assert client.closed is True

    asyncio.run(run())

    batch_client = FakeRedis()
    batch_client.publish = fail_publish
    monkeypatch.setattr(submission_events, "_redis_client", lambda: batch_client)

    async def run_batch():
        assert await submission_events.publish_batch_status(
            5, "failed", 2, 1, 1
        ) is False
        assert batch_client.closed is True

    asyncio.run(run_batch())
