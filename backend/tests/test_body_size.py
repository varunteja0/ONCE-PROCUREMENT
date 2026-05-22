"""Tests for app.middleware.body_size."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.body_size import (
    DEFAULT_JSON_LIMIT_BYTES,
    BodySizeLimitMiddleware,
)

pytestmark = pytest.mark.asyncio


def _build_app(json_limit: int, upload_limit: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        BodySizeLimitMiddleware, json_limit=json_limit, upload_limit=upload_limit
    )

    @app.post("/json")
    async def post_json(request: Request) -> dict:
        body = await request.body()
        return {"len": len(body)}

    @app.post("/upload")
    async def post_upload(request: Request) -> dict:
        body = await request.body()
        return {"len": len(body)}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


class TestJsonLimit:
    async def test_just_under_limit_accepted(self) -> None:
        limit = 4096
        app = _build_app(json_limit=limit, upload_limit=10 * limit)
        payload = {"x": "a" * (limit - 50)}
        body = json.dumps(payload).encode()
        assert len(body) < limit
        async with await _client(app) as c:
            r = await c.post("/json", content=body, headers={"content-type": "application/json"})
        assert r.status_code == 200
        assert r.json()["len"] == len(body)

    async def test_over_limit_rejected_via_content_length(self) -> None:
        limit = 1024
        app = _build_app(json_limit=limit, upload_limit=10 * limit)
        body = b"x" * (limit + 200)
        async with await _client(app) as c:
            r = await c.post(
                "/json",
                content=body,
                headers={
                    "content-type": "application/json",
                    "content-length": str(len(body)),
                },
            )
        assert r.status_code == 413
        data = r.json()
        assert data["detail"] == "request_body_too_large"
        assert data["limit_bytes"] == limit

    async def test_default_one_mib_constant(self) -> None:
        assert DEFAULT_JSON_LIMIT_BYTES == 1 * 1024 * 1024


class TestUploadLimit:
    async def test_multipart_uses_upload_limit(self) -> None:
        json_limit = 1024
        upload_limit = 64 * 1024
        app = _build_app(json_limit=json_limit, upload_limit=upload_limit)
        # 8 KiB payload: exceeds json limit but well under upload limit.
        body_part = b"y" * (8 * 1024)
        boundary = "----test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="x.bin"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + body_part + f"\r\n--{boundary}--\r\n".encode()

        async with await _client(app) as c:
            r = await c.post(
                "/upload",
                content=body,
                headers={
                    "content-type": f"multipart/form-data; boundary={boundary}",
                    "content-length": str(len(body)),
                },
            )
        assert r.status_code == 200, r.text

    async def test_octet_stream_over_upload_limit_rejected(self) -> None:
        app = _build_app(json_limit=1024, upload_limit=4096)
        body = b"z" * 5000
        async with await _client(app) as c:
            r = await c.post(
                "/upload",
                content=body,
                headers={
                    "content-type": "application/octet-stream",
                    "content-length": str(len(body)),
                },
            )
        assert r.status_code == 413
