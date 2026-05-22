"""Tests for ``app.observability`` exception handlers.

These handlers convert raw exceptions into the canonical JSON envelope. The
default :func:`tests.conftest.test_app` does NOT register them — those tests
rely on FastAPI's built-in error responses. Here we mount a dedicated app via
:func:`tests.conftest_helpers.app_with_handlers` and exercise the handlers
directly by adding throwing routes.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.observability import init_sentry, register_exception_handlers


class _Echo(BaseModel):
    n: int


def _build_app_with_throwers() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom-500")
    async def boom_500() -> dict[str, str]:
        raise HTTPException(status_code=500, detail="internal_thing_broke")

    @app.get("/boom-400")
    async def boom_400() -> dict[str, str]:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_request", "message": "nope"},
        )

    @app.get("/boom-unhandled")
    async def boom_unhandled() -> dict[str, str]:
        raise RuntimeError("unhandled-on-purpose")

    @app.post("/echo")
    async def echo(payload: _Echo) -> dict[str, int]:
        return {"n": payload.n}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://t",
    )


class TestHttpExceptionHandler:
    async def test_5xx_http_exception_returns_envelope(self) -> None:
        async with await _client(_build_app_with_throwers()) as c:
            r = await c.get("/boom-500")
        assert r.status_code == 500
        assert r.json() == {"detail": "internal_thing_broke"}

    async def test_4xx_http_exception_preserves_structured_detail(self) -> None:
        async with await _client(_build_app_with_throwers()) as c:
            r = await c.get("/boom-400")
        assert r.status_code == 400
        body = r.json()
        assert body["detail"] == {"code": "bad_request", "message": "nope"}


class TestUnhandledExceptionHandler:
    async def test_unhandled_exception_returns_500_envelope(self) -> None:
        async with await _client(_build_app_with_throwers()) as c:
            r = await c.get("/boom-unhandled")
        assert r.status_code == 500
        assert r.json() == {"detail": "internal_server_error"}


class TestValidationHandler:
    async def test_validation_error_returns_422_with_errors_list(self) -> None:
        async with await _client(_build_app_with_throwers()) as c:
            r = await c.post("/echo", json={"n": "not-an-int"})
        assert r.status_code == 422
        body = r.json()
        assert isinstance(body["detail"], list)
        assert any("n" in err.get("loc", []) for err in body["detail"])


class TestSentryInit:
    def test_init_sentry_noop_when_dsn_blank(self) -> None:
        assert (
            init_sentry(
                dsn="",
                environment="test",
                release="0.0.0",
                traces_sample_rate=0.1,
            )
            is False
        )

    def test_init_sentry_noop_when_dsn_whitespace(self) -> None:
        assert (
            init_sentry(
                dsn="   ",
                environment="test",
                release="0.0.0",
                traces_sample_rate=0.1,
            )
            is False
        )

    def test_init_sentry_full_path_initializes_and_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover the success branch: real DSN, sentry_sdk.init mocked so we
        don't actually phone home. The second call must short-circuit via the
        ``_SENTRY_INITIALIZED`` guard.
        """

        import sentry_sdk

        import app.observability as obs

        monkeypatch.setattr(obs, "_SENTRY_INITIALIZED", False)

        calls: list[dict[str, object]] = []

        def _fake_init(**kwargs: object) -> None:
            calls.append(kwargs)

        monkeypatch.setattr(sentry_sdk, "init", _fake_init)

        first = init_sentry(
            dsn="https://public@example.com/1",
            environment="test",
            release="1.2.3",
            traces_sample_rate=0.25,
        )
        second = init_sentry(
            dsn="https://public@example.com/1",
            environment="test",
            release="1.2.3",
            traces_sample_rate=0.25,
        )

        assert first is True
        assert second is False
        assert len(calls) == 1
        assert calls[0]["environment"] == "test"
        assert calls[0]["release"] == "1.2.3"
        assert calls[0]["traces_sample_rate"] == 0.25
