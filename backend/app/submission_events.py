"""Redis Pub/Sub events for cross-process submission status updates."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from typing import Any, AsyncIterator

from app.config import settings


def submission_event_channel(submission_id: int) -> str:
    return f"submission-events:{submission_id}"


def batch_event_channel(batch_id: int) -> str:
    return f"grading-batch-events:{batch_id}"


def _redis_client() -> Any:
    import redis.asyncio as aioredis

    return aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


async def publish_submission_status(
    submission_id: int,
    status: str,
    reason: str | None = None,
) -> bool:
    payload = {
        "type": "submission.status",
        "submission_id": submission_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        payload["reason"] = reason

    client = None
    try:
        client = _redis_client()
        await client.publish(
            submission_event_channel(submission_id),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        return True
    except Exception:
        return False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


async def publish_batch_status(
    batch_id: int,
    status: str,
    total_submissions: int,
    completed_submissions: int,
    failed_submissions: int,
) -> bool:
    finished = completed_submissions + failed_submissions
    payload = {
        "type": "grading_batch.status",
        "batch_id": batch_id,
        "status": status,
        "total_submissions": total_submissions,
        "completed_submissions": completed_submissions,
        "failed_submissions": failed_submissions,
        "finished_submissions": finished,
        "progress_percent": round(finished * 100 / total_submissions, 1)
        if total_submissions
        else 100.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    client = None
    try:
        client = _redis_client()
        await client.publish(
            batch_event_channel(batch_id),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        return True
    except Exception:
        return False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


@asynccontextmanager
async def subscribe_submission_events(
    submission_id: int,
) -> AsyncIterator[Any]:
    client = _redis_client()
    pubsub = client.pubsub()
    channel = submission_event_channel(submission_id)
    try:
        await pubsub.subscribe(channel)
        yield pubsub
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await client.aclose()


@asynccontextmanager
async def subscribe_batch_events(batch_id: int) -> AsyncIterator[Any]:
    client = _redis_client()
    pubsub = client.pubsub()
    channel = batch_event_channel(batch_id)
    try:
        await pubsub.subscribe(channel)
        yield pubsub
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await client.aclose()
