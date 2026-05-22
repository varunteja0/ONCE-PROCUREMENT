"""Tests for the SlowAPI rate-limit middleware wiring.

The default ``test_app`` fixture intentionally omits SlowAPI to keep tests
hermetic. Here we build a minimal app with the same handler/middleware setup
the production ``create_app`` uses and verify that exceeding the configured
limit returns a structured 429.

The limiter is configured per-test at a tiny budget so the assertions are
deterministic and fast.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

pytestmark = pytest.mark.asyncio


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate_limit_exceeded", "limit": str(exc.detail)},
    )


def _build_app(limit: str = "2/minute") -> FastAPI:
    app = FastAPI()
    limiter = Limiter(key_func=get_remote_address, default_limits=[limit])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    async def ping(request: Request) -> dict[str, str]:  # noqa: ARG001
        return {"ok": "pong"}

    return app


async def _new_client(limit: str = "2/minute") -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=_build_app(limit)),
        base_url="http://t",
    )


class TestRateLimit:
    async def test_requests_under_limit_pass(self) -> None:
        async with await _new_client("3/minute") as c:
            r1 = await c.get("/ping")
            r2 = await c.get("/ping")
        assert r1.status_code == 200
        assert r2.status_code == 200

    async def test_request_exceeding_limit_returns_429(self) -> None:
        async with await _new_client("2/minute") as c:
            for _ in range(2):
                ok = await c.get("/ping")
                assert ok.status_code == 200
            blocked = await c.get("/ping")
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["detail"] == "rate_limit_exceeded"
        assert "limit" in body

    async def test_429_response_includes_limit_string(self) -> None:
        async with await _new_client("1/minute") as c:
            await c.get("/ping")
            blocked = await c.get("/ping")
        assert blocked.status_code == 429
        # Limit string mentions the requested cadence.
        assert "1" in blocked.json()["limit"]
