"""Tests for the RFC-9457 Problem error envelope."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.middleware.request_id import RequestIDMiddleware
from app.utils.errors import (
    PROBLEM_CONTENT_TYPE,
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    install_error_handlers,
)

pytestmark = pytest.mark.asyncio


class _Echo(BaseModel):
    n: int


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    install_error_handlers(app)

    @app.get("/raises-http-404")
    async def raises_http_404() -> dict[str, str]:
        raise HTTPException(status_code=404, detail="not_here")

    @app.get("/raises-http-400-dict")
    async def raises_http_400_dict() -> dict[str, str]:
        raise HTTPException(
            status_code=400, detail={"code": "bad_input", "message": "nope"}
        )

    @app.get("/raises-http-500")
    async def raises_http_500() -> dict[str, str]:
        raise HTTPException(status_code=500, detail="internal")

    @app.get("/raises-domain-notfound")
    async def raises_domain_notfound() -> dict[str, str]:
        raise NotFoundError(detail="missing widget")

    @app.get("/raises-domain-conflict")
    async def raises_domain_conflict() -> dict[str, str]:
        raise ConflictError(detail="dup")

    @app.get("/raises-domain-precondition")
    async def raises_domain_precondition() -> dict[str, str]:
        raise PreconditionFailedError()

    @app.get("/raises-unhandled")
    async def raises_unhandled() -> dict[str, str]:
        raise RuntimeError("kaboom")

    @app.post("/echo")
    async def echo(payload: _Echo) -> dict[str, int]:
        return {"n": payload.n}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://t",
    )


class TestEnvelopeShape:
    async def test_http_404_returns_problem_with_all_fields(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-http-404")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        body = r.json()
        assert body["status"] == 404
        assert body["title"] == "Not found"
        assert body["type"].startswith("https://docs.getonce.com/errors/")
        assert body["type"].endswith("/not-found")
        assert body["instance"] == "/raises-http-404"
        assert body["trace_id"]
        # Backward-compat: legacy detail field still present.
        assert body["detail"] == "not_here"

    async def test_http_400_preserves_structured_detail(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-http-400-dict")
        body = r.json()
        assert r.status_code == 400
        assert body["detail"] == {"code": "bad_input", "message": "nope"}
        assert body["title"] == "Bad request"

    async def test_http_500_returns_envelope(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-http-500")
        assert r.status_code == 500
        body = r.json()
        assert body["title"] == "Internal server error"
        assert body["detail"] == "internal"
        assert body["trace_id"]


class TestDomainErrors:
    async def test_not_found_error_maps_to_404(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-domain-notfound")
        assert r.status_code == 404
        body = r.json()
        assert body["type"].endswith("/not-found")
        assert body["title"] == "Resource not found"
        assert body["detail"] == "missing widget"

    async def test_conflict_error_maps_to_409(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-domain-conflict")
        assert r.status_code == 409
        assert r.json()["type"].endswith("/conflict")

    async def test_precondition_failed_maps_to_412(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-domain-precondition")
        assert r.status_code == 412
        assert r.json()["type"].endswith("/precondition-failed")


class TestUnhandled:
    async def test_unhandled_exception_returns_envelope_500(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/raises-unhandled")
        assert r.status_code == 500
        body = r.json()
        assert body["title"] == "Internal server error"
        assert body["status"] == 500
        # Doesn't leak the original exception message.
        assert "kaboom" not in str(body)


class TestValidation:
    async def test_validation_error_includes_errors_array(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.post("/echo", json={"n": "not-an-int"})
        assert r.status_code == 422
        body = r.json()
        assert body["status"] == 422
        assert body["title"] == "Unprocessable entity"
        assert isinstance(body["errors"], list)
        assert any("n" in err["loc"] for err in body["errors"])
        # Legacy `detail` is still the raw pydantic list.
        assert isinstance(body["detail"], list)


class TestTypeUriWellFormed:
    async def test_all_type_uris_are_http_urls(self) -> None:
        async with await _client(_build_app()) as c:
            paths = [
                "/raises-http-404",
                "/raises-http-400-dict",
                "/raises-domain-conflict",
                "/raises-domain-precondition",
                "/raises-unhandled",
            ]
            for p in paths:
                r = await c.get(p)
                t = r.json()["type"]
                assert t.startswith("https://")
                assert "/errors/" in t
