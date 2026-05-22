"""AccessLogMiddleware tests."""

from __future__ import annotations

import logging

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.utils.logging import configure_logging

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/hello")
    async def hello() -> dict[str, str]:
        return {"hello": "world"}

    @app.get("/v1/health/live")
    async def live() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/metrics")
    async def metrics() -> dict[str, str]:
        return {"metrics": "ok"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("kaboom")

    return app


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def capture(monkeypatch):  # type: ignore[no-untyped-def]
    configure_logging(force=True)
    events: list[dict] = []

    def _proc(_, __, event_dict):  # type: ignore[no-untyped-def]
        events.append(dict(event_dict))
        return event_dict

    cfg = structlog.get_config()
    structlog.configure(
        processors=[_proc, *cfg["processors"]],
        wrapper_class=cfg["wrapper_class"],
        logger_factory=cfg["logger_factory"],
        context_class=cfg["context_class"],
        cache_logger_on_first_use=False,
    )
    yield events
    structlog.configure(**cfg)


async def test_logs_normal_request_with_required_fields(capture) -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/hello", headers={"user-agent": "pytest-ua"})
    assert resp.status_code == 200

    access_events = [e for e in capture if e.get("event") == "http_access"]
    assert len(access_events) == 1
    ev = access_events[0]
    for key in (
        "method", "path", "route_template", "status", "duration_ms",
        "client_ip", "user_agent", "bytes_in", "bytes_out", "request_id",
    ):
        assert key in ev, f"missing {key}"
    assert ev["method"] == "GET"
    assert ev["path"] == "/hello"
    assert ev["route_template"] == "/hello"
    assert ev["status"] == 200
    assert ev["user_agent"] == "pytest-ua"


async def test_skips_health_live_and_metrics(capture) -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.get("/v1/health/live")
        await ac.get("/metrics")

    access_events = [e for e in capture if e.get("event") == "http_access"]
    assert access_events == []


async def test_logs_500_at_error_level(capture) -> None:
    app = _build_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as ac:
        await ac.get("/boom")

    access_events = [e for e in capture if e.get("event") == "http_access"]
    assert len(access_events) == 1
    assert access_events[0]["status"] == 500


async def test_does_not_log_authorization_header(capture) -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.get("/hello", headers={"authorization": "Bearer SECRETTOKEN"})

    access_events = [e for e in capture if e.get("event") == "http_access"]
    assert len(access_events) == 1
    flat = repr(access_events[0])
    assert "SECRETTOKEN" not in flat
    assert "authorization" not in {k.lower() for k in access_events[0].keys()}
