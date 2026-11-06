"""Tests for API rate limiting and client identity handling."""

import asyncio
from types import SimpleNamespace

from app import security


class FakeRequest:
    def __init__(self, path="/api/test", headers=None):
        self.url = SimpleNamespace(path=path)
        self.headers = headers or {}
        self.client = SimpleNamespace(host="127.0.0.1")


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.headers = {}


def test_local_rate_limiter_blocks_after_limit():
    limiter = security.LocalRateLimiter()

    async def run():
        first = await limiter.check("client", limit=2, window_seconds=60)
        second = await limiter.check("client", limit=2, window_seconds=60)
        third = await limiter.check("client", limit=2, window_seconds=60)
        assert first.allowed and first.remaining == 1
        assert second.allowed and second.remaining == 0
        assert not third.allowed and third.retry_after > 0

    asyncio.run(run())


def test_redis_rate_limiter_uses_atomic_counter(monkeypatch):
    class FakeRedis:
        async def eval(self, script, key_count, key, window_seconds):
            assert script == security.RATE_LIMIT_SCRIPT
            assert key_count == 1
            assert key.startswith("rate-limit:")
            assert window_seconds == 60
            return [3, 37]

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *args, **kwargs: FakeRedis()
    )
    result = asyncio.run(security._redis_rate_limit("rate-limit:test", 5, 60))
    assert result.allowed
    assert result.remaining == 2
    assert result.retry_after == 37


def test_rate_limiter_falls_back_when_redis_fails(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("redis unavailable")

    fallback_result = security.RateLimitResult(True, 5, 4, 60)

    async def fallback(*args, **kwargs):
        return fallback_result

    monkeypatch.setattr(security, "_redis_rate_limit", unavailable)
    monkeypatch.setattr(security.local_rate_limiter, "check", fallback)
    result = asyncio.run(security.check_rate_limit("client", "login", 5))
    assert result is fallback_result


def test_rate_limit_middleware_adds_headers(monkeypatch):
    async def allowed(*args, **kwargs):
        return security.RateLimitResult(True, 60, 59, 60)

    async def call_next(request):
        return FakeResponse()

    monkeypatch.setattr(security, "check_rate_limit", allowed)
    response = asyncio.run(
        security.enforce_rate_limits(FakeRequest(), call_next)
    )
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert response.headers["X-RateLimit-Remaining"] == "59"


def test_rate_limit_middleware_returns_429(monkeypatch):
    async def denied(*args, **kwargs):
        return security.RateLimitResult(False, 5, 0, 42)

    async def should_not_run(request):
        raise AssertionError("blocked requests must not reach the endpoint")

    monkeypatch.setattr(security, "check_rate_limit", denied)
    response = asyncio.run(
        security.enforce_rate_limits(FakeRequest("/api/auth/login"), should_not_run)
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.headers["X-RateLimit-Limit"] == "5"


def test_non_api_routes_are_not_limited(monkeypatch):
    async def fail_if_checked(*args, **kwargs):
        raise AssertionError("non-API routes should bypass rate limiting")

    async def call_next(request):
        return FakeResponse(204)

    monkeypatch.setattr(security, "check_rate_limit", fail_if_checked)
    response = asyncio.run(
        security.enforce_rate_limits(FakeRequest("/metrics"), call_next)
    )
    assert response.status_code == 204


def test_request_id_accepts_only_uuid_and_client_id_is_hashed(monkeypatch):
    valid = "123e4567-e89b-12d3-a456-426614174000"
    assert security.request_id_from_header(valid) == valid
    generated = security.request_id_from_header("line-break\nforged")
    assert generated != "line-break\nforged"
    assert len(generated) == 36

    request = FakeRequest(headers={"X-Forwarded-For": "203.0.113.4"})
    monkeypatch.setattr(security.settings, "TRUST_PROXY_HEADERS", True)
    client_id = security.audit_client_id(request)
    assert client_id != "203.0.113.4"
    assert len(client_id) == 16
