"""TimingMiddleware tests."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from prometheus_client import generate_latest

from app.middleware.timing import TimingMiddleware
from app.observability_extras import DEFAULT_REGISTRY

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TimingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "1"}

    return app


async def test_server_timing_header_present() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ping")
    assert resp.status_code == 200
    header = resp.headers.get("server-timing")
    assert header
    assert re.match(r"^total;dur=\d+\.\d+$", header)


async def test_histogram_records_request() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.get("/ping")

    payload = generate_latest(DEFAULT_REGISTRY).decode("utf-8")
    # The histogram should have observed at least one sample for /ping.
    assert "http_request_duration_seconds_count" in payload
    assert 'route="/ping"' in payload
    assert "http_requests_total" in payload
    assert 'method="GET"' in payload
