"""RequestIDMiddleware tests."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.request_id import REQUEST_ID_HEADER, RequestIDMiddleware

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo(request: Request):  # type: ignore[no-untyped-def]
        return {"request_id": request.state.request_id}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_generates_id_when_missing() -> None:
    app = _build_app()
    async with await _client(app) as ac:
        resp = await ac.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid
    assert re.match(r"^[A-Za-z0-9_\-]{8,128}$", rid)
    assert resp.json()["request_id"] == rid


async def test_propagates_incoming_id() -> None:
    app = _build_app()
    incoming = "req-abcdef-1234567890"
    async with await _client(app) as ac:
        resp = await ac.get("/echo", headers={REQUEST_ID_HEADER: incoming})
    assert resp.headers.get(REQUEST_ID_HEADER) == incoming
    assert resp.json()["request_id"] == incoming


async def test_rejects_garbage_and_regenerates() -> None:
    app = _build_app()
    async with await _client(app) as ac:
        resp = await ac.get("/echo", headers={REQUEST_ID_HEADER: "bad id with spaces!!!"})
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid
    assert rid != "bad id with spaces!!!"
    assert re.match(r"^[A-Za-z0-9_\-]{8,128}$", rid)
