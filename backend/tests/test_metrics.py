"""Metrics endpoint tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.metrics import router as metrics_router

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(metrics_router)
    return app


async def test_metrics_returns_text_when_open(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # A handful of canonical metric names must be present (registered at import).
    for name in (
        "http_requests_total",
        "http_request_duration_seconds",
        "submissions_total",
        "auth_logins_total",
        "csrf_failures_total",
        "receipts_signed_total",
        "celery_tasks_total",
    ):
        assert name in body, f"missing metric {name}"


async def test_metrics_disabled_returns_404(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "false")
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/metrics")
    assert resp.status_code == 404


async def test_metrics_token_required(monkeypatch) -> None:
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/metrics")
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate", "").lower().startswith("bearer")

        resp2 = await ac.get("/metrics", headers={"authorization": "Bearer wrong"})
        assert resp2.status_code == 401

        resp3 = await ac.get("/metrics", headers={"authorization": "Bearer s3cret"})
        assert resp3.status_code == 200
