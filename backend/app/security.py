"""HTTP security controls shared by the FastAPI application."""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings


RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class LocalRateLimiter:
    """Small failover limiter used only while Redis is unavailable."""

    def __init__(self):
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        async with self._lock:
            started_at, count = self._windows.get(key, (now, 0))
            if now - started_at >= window_seconds:
                started_at, count = now, 0
            count += 1
            self._windows[key] = (started_at, count)

        retry_after = max(1, int(window_seconds - (now - started_at)))
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(limit - count, 0),
            retry_after=retry_after,
        )


local_rate_limiter = LocalRateLimiter()


def client_identity(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def audit_client_id(request: Request) -> str:
    identity = client_identity(request)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def request_id_from_header(value: str | None) -> str:
    if value:
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError):
            pass
    return str(uuid.uuid4())


def _rate_limit_key(identity: str, bucket: str, window_seconds: int) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    window = int(time.time()) // window_seconds
    return f"rate-limit:{bucket}:{digest}:{window}"


async def _redis_rate_limit(
    key: str, limit: int, window_seconds: int
) -> RateLimitResult:
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        count, ttl = await client.eval(RATE_LIMIT_SCRIPT, 1, key, window_seconds)
    finally:
        await client.aclose()

    count = int(count)
    retry_after = max(int(ttl), 1)
    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=max(limit - count, 0),
        retry_after=retry_after,
    )


async def check_rate_limit(
    identity: str, bucket: str, limit: int, window_seconds: int = 60
) -> RateLimitResult:
    key = _rate_limit_key(identity, bucket, window_seconds)
    try:
        return await _redis_rate_limit(key, limit, window_seconds)
    except Exception:
        return await local_rate_limiter.check(key, limit, window_seconds)


def _limit_for_request(request: Request) -> tuple[str, int] | None:
    if request.url.path == "/api/auth/login":
        return "login", max(settings.LOGIN_RATE_LIMIT_PER_MINUTE, 1)
    if request.url.path.startswith("/api/"):
        return "api", max(settings.API_RATE_LIMIT_PER_MINUTE, 1)
    return None


async def enforce_rate_limits(request: Request, call_next):
    configured_limit = _limit_for_request(request)
    if configured_limit is None:
        return await call_next(request)

    bucket, limit = configured_limit
    result = await check_rate_limit(client_identity(request), bucket, limit)
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
    }
    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after)
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后重试"},
            headers=headers,
        )

    response = await call_next(request)
    response.headers.update(headers)
    return response
