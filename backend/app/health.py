import time
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text
from app.database import AsyncSession

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/api/health")
async def health():
    checks = {}
    overall = "ok"

    try:
        async with AsyncSession() as session:
            t0 = time.time()
            await session.execute(text("SELECT 1"))
            checks["mysql"] = {
                "status": "up",
                "latency_ms": round((time.time() - t0) * 1000, 1),
            }
    except Exception as e:
        checks["mysql"] = {"status": "down", "error": str(e)}
        overall = "degraded"

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url("redis://:redis123@redis:6379/0")
        t0 = time.time()
        await r.ping()
        checks["redis"] = {
            "status": "up",
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
        await r.aclose()
    except Exception:
        checks["redis"] = {"status": "down"}
        overall = "degraded"

    try:
        import aio_pika

        connection = await aio_pika.connect_robust("amqp://grader:grader_pass@rabbitmq:5672//")
        await connection.close()
        checks["rabbitmq"] = {"status": "up"}
    except Exception:
        checks["rabbitmq"] = {"status": "down"}
        overall = "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - _start_time),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
