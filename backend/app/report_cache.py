"""Best-effort Redis cache for learning reports."""

from __future__ import annotations

import json

from app.config import settings


def student_report_cache_key(student_id: int, subject_id: int | None = None) -> str:
    subject = subject_id if subject_id is not None else "all"
    return f"learning-report:student:{student_id}:{subject}"


def class_report_cache_key(class_id: int, subject_id: int | None = None) -> str:
    subject = subject_id if subject_id is not None else "all"
    return f"learning-report:class:{class_id}:{subject}"


async def get_report(key: str) -> dict | None:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            value = await client.get(key)
        finally:
            await client.aclose()
        if not value:
            return None
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def set_report(key: str, report: dict) -> bool:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await client.set(
                key,
                json.dumps(report, ensure_ascii=False, separators=(",", ":")),
                ex=max(settings.REPORT_CACHE_TTL_SECONDS, 1),
            )
        finally:
            await client.aclose()
        return True
    except Exception:
        return False


async def _delete_pattern(pattern: str) -> int:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            keys = [key async for key in client.scan_iter(match=pattern)]
            if not keys:
                return 0
            return int(await client.delete(*keys))
        finally:
            await client.aclose()
    except Exception:
        return 0


async def invalidate_student_reports(student_id: int) -> int:
    return await _delete_pattern(f"learning-report:student:{student_id}:*")


async def invalidate_class_reports(class_id: int) -> int:
    return await _delete_pattern(f"learning-report:class:{class_id}:*")


async def invalidate_report_cache(student_id: int, class_id: int) -> int:
    deleted = await invalidate_student_reports(student_id)
    return deleted + await invalidate_class_reports(class_id)
