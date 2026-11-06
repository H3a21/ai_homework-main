"""Unit tests for security helpers, cache behavior, and service health checks."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jose import jwt

from app import auth, health, report_cache
from app.config import settings
from app.dependencies import get_current_user, require_role
from app.ocr_client import ocr_image
from app.schemas import LoginRequest, RegisterRequest


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, result=None):
        self.result = result
        self.added = []

    async def execute(self, statement):
        return FakeResult(self.result)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None

    async def refresh(self, value):
        value.id = 7


class FakeRequest:
    def __init__(self):
        self.state = SimpleNamespace()


def test_password_hashing_and_token_types():
    hashed = auth._hash_password("secret123")
    assert hashed != "secret123"
    assert auth._verify_password("secret123", hashed)
    assert not auth._verify_password("wrong", hashed)

    access = jwt.decode(
        auth._create_access_token({"sub": "7", "role": "student"}),
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    refresh = jwt.decode(
        auth._create_refresh_token({"sub": "7", "role": "student"}),
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert access["type"] == "access"
    assert refresh["type"] == "refresh"


def test_register_login_and_refresh_flow():
    async def run():
        db = FakeDB()
        registered = await auth.register(
            FakeRequest(),
            RegisterRequest(
                username="student_test",
                password="secret123",
                display_name="Test Student",
                role="student",
            ),
            db,
        )
        assert registered.token_type == "bearer"
        user = db.added[0]
        assert auth._verify_password("secret123", user.password_hash)

        logged_in = await auth.login(
            FakeRequest(),
            LoginRequest(username="student_test", password="secret123"),
            FakeDB(SimpleNamespace(
                id=7,
                username="student_test",
                password_hash=user.password_hash,
                role="student",
            )),
        )
        refreshed = await auth.refresh(
            FakeRequest(),
            auth.RefreshRequest(refresh_token=logged_in.refresh_token)
        )
        assert logged_in.access_token
        assert refreshed.access_token

    asyncio.run(run())


def test_login_rejects_bad_password_and_refresh_rejects_access_token():
    async def run():
        user = SimpleNamespace(
            id=7,
            username="student_test",
            password_hash=auth._hash_password("secret123"),
            role="student",
        )
        with pytest.raises(HTTPException) as login_error:
            await auth.login(
                FakeRequest(),
                LoginRequest(username="student_test", password="wrong"),
                FakeDB(user),
            )
        assert login_error.value.status_code == 401

        access = auth._create_access_token({"sub": "7", "role": "student"})
        with pytest.raises(HTTPException) as refresh_error:
            await auth.refresh(FakeRequest(), auth.RefreshRequest(refresh_token=access))
        assert refresh_error.value.status_code == 401

    asyncio.run(run())


def test_current_user_dependency_covers_auth_failures_and_success():
    async def run():
        with pytest.raises(HTTPException) as missing:
            await get_current_user(FakeRequest(), None, FakeDB())
        assert missing.value.status_code == 401

        bad_credentials = SimpleNamespace(credentials="invalid")
        with pytest.raises(HTTPException) as invalid:
            await get_current_user(FakeRequest(), bad_credentials, FakeDB())
        assert invalid.value.status_code == 401

        refresh_token = auth._create_refresh_token({"sub": "7", "role": "student"})
        with pytest.raises(HTTPException) as wrong_type:
            await get_current_user(
                FakeRequest(), SimpleNamespace(credentials=refresh_token), FakeDB()
            )
        assert wrong_type.value.status_code == 401

        token = auth._create_access_token({"sub": "7", "role": "student"})
        user = SimpleNamespace(id=7, role="student")
        request = FakeRequest()
        assert await get_current_user(
            request, SimpleNamespace(credentials=token), FakeDB(user)
        ) is user
        assert request.state.actor_id == 7

        with pytest.raises(HTTPException) as missing_user:
            await get_current_user(
                FakeRequest(), SimpleNamespace(credentials=token), FakeDB()
            )
        assert missing_user.value.status_code == 404

    asyncio.run(run())


def test_require_role_enforces_teacher_or_student():
    async def run():
        checker = require_role("teacher")
        teacher = SimpleNamespace(role="teacher")
        assert await checker(teacher) is teacher
        with pytest.raises(HTTPException) as error:
            await checker(SimpleNamespace(role="student"))
        assert error.value.status_code == 403

    asyncio.run(run())


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}
        self.closed = False

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex):
        self.values[key] = value
        self.expire = ex

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            deleted += int(self.values.pop(key, None) is not None)
        return deleted

    async def scan_iter(self, match):
        prefix = match.rstrip("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    async def aclose(self):
        self.closed = True


def test_report_cache_keys_and_redis_round_trip(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *args, **kwargs: redis_client
    )

    async def run():
        assert report_cache.student_report_cache_key(7) == "learning-report:student:7:all"
        assert report_cache.class_report_cache_key(3, 2) == "learning-report:class:3:2"
        key = report_cache.student_report_cache_key(7, 1)
        assert await report_cache.get_report(key) is None
        assert await report_cache.set_report(key, {"score": 9})
        assert await report_cache.get_report(key) == {"score": 9}
        assert await report_cache.invalidate_student_reports(7) == 1

    asyncio.run(run())


def test_report_cache_fails_closed_when_redis_or_json_fails(monkeypatch):
    monkeypatch.setattr(
        "redis.asyncio.from_url", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
    )

    async def run():
        assert await report_cache.get_report("key") is None
        assert not await report_cache.set_report("key", {})
        assert await report_cache.invalidate_class_reports(3) == 0

    asyncio.run(run())


def test_health_returns_ok_when_dependencies_are_available(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, statement):
            return None

    class Redis:
        async def ping(self):
            return True

        async def aclose(self):
            return None

    class RabbitConnection:
        async def close(self):
            return None

    monkeypatch.setattr(health, "AsyncSession", Session)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: Redis())
    monkeypatch.setattr(
        "aio_pika.connect_robust",
        lambda *args, **kwargs: asyncio.sleep(0, result=RabbitConnection()),
    )
    result = asyncio.run(health.health())
    assert result["status"] == "ok"
    assert all(item["status"] == "up" for item in result["checks"].values())


def test_ocr_client_sends_multipart_request(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "recognized"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, files):
            assert url.endswith("/ocr")
            assert files["image"][0] == "answer.png"
            return Response()

    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: Client())
    result = asyncio.run(ocr_image(b"png", "answer.png"))
    assert result == {"text": "recognized"}


def test_request_schema_rejects_short_password():
    with pytest.raises(ValueError):
        RegisterRequest(
            username="abc",
            password="short",
            display_name="Student",
        )
    assert LoginRequest(username="abc", password="x").username == "abc"
