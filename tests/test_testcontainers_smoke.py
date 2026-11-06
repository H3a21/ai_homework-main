"""Isolated infrastructure smoke tests powered by Testcontainers."""

import os

import pytest
from redis import Redis
from testcontainers.redis import RedisContainer


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_TESTCONTAINERS") != "1",
        reason="set RUN_TESTCONTAINERS=1 to start Docker test containers",
    ),
]


def test_redis_container_round_trip():
    with RedisContainer("redis:7-alpine") as container:
        client = Redis(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(6379)),
            decode_responses=True,
        )
        try:
            client.set("quality-002", "ok", ex=30)
            assert client.get("quality-002") == "ok"
        finally:
            client.close()
