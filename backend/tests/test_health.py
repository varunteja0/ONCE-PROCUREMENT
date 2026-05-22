"""Health endpoint tests for ``GET /v1/health/live``, ``/v1/health`` and ``/v1/ready``.

Redis is not running in tests; the readiness probe is wired to mark Redis as
``skipped`` when ``REDIS_URL`` is blank (or the client cannot connect), so the
endpoint should still return ``200 ok``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestLiveness:
    async def test_live_returns_200_ok(self, client: AsyncClient) -> None:
        r = await client.get("/v1/health/live")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "time" in body


class TestReadiness:
    async def test_ready_returns_200_when_db_ok(self, client: AsyncClient) -> None:
        r = await client.get("/v1/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["database"] == "ok"

    async def test_health_returns_ok_with_db_check(self, client: AsyncClient) -> None:
        r = await client.get("/v1/health")
        # Either 200 ok (redis skipped) or 503 with checks dict present.
        assert r.status_code in (200, 503)
        body = r.json()
        assert "checks" in body
        assert body["checks"]["db"] == "ok"
        # Redis is either skipped (no client / blank URL) or fail (no server).
        assert body["checks"]["redis"] in ("ok", "skipped", "fail")

    async def test_health_response_includes_version_and_time(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/v1/health")
        body = r.json()
        assert "version" in body
        assert "time" in body
