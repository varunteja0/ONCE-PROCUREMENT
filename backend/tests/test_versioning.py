"""Tests for API version negotiation."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.versioning import (
    DEFAULT_API_VERSION,
    ApiVersioningMiddleware,
    parse_accept_version,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiVersioningMiddleware, supported_versions=("v1", "v2"))

    @app.get("/echo")
    async def echo() -> dict[str, str]:
        return {"ok": "true"}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


class TestParseAcceptVersion:
    def test_default_when_header_absent(self) -> None:
        assert parse_accept_version(None) == DEFAULT_API_VERSION

    def test_default_when_header_empty(self) -> None:
        assert parse_accept_version("") == DEFAULT_API_VERSION

    def test_default_when_no_match(self) -> None:
        assert parse_accept_version("application/json") == DEFAULT_API_VERSION

    def test_parses_v1(self) -> None:
        assert parse_accept_version("application/vnd.once.v1+json") == "v1"

    def test_parses_v2_when_supported(self) -> None:
        assert (
            parse_accept_version(
                "application/vnd.once.v2+json", supported=("v1", "v2")
            )
            == "v2"
        )

    def test_falls_back_when_version_unsupported(self) -> None:
        assert (
            parse_accept_version("application/vnd.once.v99+json", supported=("v1",))
            == "v1"
        )

    def test_handles_compound_accept_header(self) -> None:
        assert (
            parse_accept_version(
                "text/html, application/vnd.once.v1+json; q=0.9"
            )
            == "v1"
        )

    def test_is_case_insensitive(self) -> None:
        assert parse_accept_version("APPLICATION/VND.ONCE.V1+JSON") == "v1"


class TestVersioningMiddleware:
    async def test_default_version_response_header(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/echo")
        assert r.status_code == 200
        assert r.headers["X-API-Version"] == "v1"

    async def test_explicit_v1_accept_yields_v1(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get(
                "/echo", headers={"Accept": "application/vnd.once.v1+json"}
            )
        assert r.headers["X-API-Version"] == "v1"

    async def test_explicit_v2_accept_yields_v2(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get(
                "/echo", headers={"Accept": "application/vnd.once.v2+json"}
            )
        assert r.headers["X-API-Version"] == "v2"

    async def test_unknown_version_falls_back_to_default(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get(
                "/echo", headers={"Accept": "application/vnd.once.v99+json"}
            )
        assert r.headers["X-API-Version"] == "v1"

    async def test_request_state_carries_version(self) -> None:
        app = FastAPI()
        app.add_middleware(ApiVersioningMiddleware)

        @app.get("/version")
        async def version(request: Request) -> dict[str, str]:
            return {"v": request.state.api_version}

        async with await _client(app) as c:
            r = await c.get(
                "/version", headers={"Accept": "application/vnd.once.v1+json"}
            )
        assert r.json() == {"v": "v1"}
