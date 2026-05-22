"""CSRF middleware tests.

The CSRF middleware enforces double-submit-cookie protection for browser
clients. These tests cover:

* bypass via Bearer authentication
* bypass via configured prefixes (``/v1/auth/*``, ``/health``, ``/verify/*``)
* safe methods always pass
* state-changing requests reject when cookie or header is missing
* cookie/header mismatch is rejected
* GET requests issue a CSRF cookie when missing
* matching cookie + header passes and the response is honored
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRFMiddleware,
)

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/x")
    async def get_x() -> dict[str, str]:
        return {"ok": "get"}

    @app.post("/x")
    async def post_x() -> dict[str, str]:
        return {"ok": "post"}

    @app.put("/x")
    async def put_x() -> dict[str, str]:
        return {"ok": "put"}

    @app.delete("/x")
    async def del_x() -> dict[str, str]:
        return {"ok": "del"}

    @app.post("/v1/auth/login")
    async def login() -> dict[str, str]:
        return {"ok": "login"}

    @app.post("/v1/public/something")
    async def public_thing() -> dict[str, str]:
        return {"ok": "public"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"ok": "health"}

    return app


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t")


class TestSafeMethodsBypass:
    async def test_get_without_cookie_passes(self) -> None:
        async with await _new_client() as c:
            r = await c.get("/x")
        assert r.status_code == 200

    async def test_get_response_issues_csrf_cookie(self) -> None:
        async with await _new_client() as c:
            r = await c.get("/x")
        cookie = r.cookies.get(CSRF_COOKIE_NAME)
        assert cookie is not None and len(cookie) > 0

    async def test_options_request_bypasses(self) -> None:
        async with await _new_client() as c:
            r = await c.request("OPTIONS", "/x")
        # OPTIONS may 405 from FastAPI (no handler), but CSRF should NOT
        # have returned 403 — the response must not be the CSRF rejection.
        assert r.status_code != 403


class TestBearerBypass:
    async def test_post_with_bearer_token_bypasses_csrf(self) -> None:
        async with await _new_client() as c:
            r = await c.post("/x", headers={"Authorization": "Bearer abc123"})
        assert r.status_code == 200

    async def test_bearer_header_case_insensitive(self) -> None:
        async with await _new_client() as c:
            r = await c.post(
                "/x", headers={"AUTHORIZATION": "bearer abc"}
            )
        assert r.status_code == 200


class TestPathBypass:
    @pytest.mark.parametrize(
        "path",
        [
            "/v1/auth/login",
            "/v1/public/something",
            "/health",
        ],
    )
    async def test_bypassed_paths_skip_csrf(self, path: str) -> None:
        async with await _new_client() as c:
            r = await c.post(path)
        assert r.status_code in (200, 405), r.text


class TestRejection:
    @pytest.mark.parametrize("method", ["post", "put", "delete"])
    async def test_state_change_without_cookie_returns_403(self, method: str) -> None:
        async with await _new_client() as c:
            r = await c.request(method, "/x")
        assert r.status_code == 403
        assert "csrf" in r.json()["detail"].lower()

    async def test_cookie_present_but_header_missing_returns_403(self) -> None:
        async with await _new_client() as c:
            c.cookies.set(CSRF_COOKIE_NAME, "tok-abc")
            r = await c.post("/x")
        assert r.status_code == 403

    async def test_cookie_header_mismatch_returns_403(self) -> None:
        async with await _new_client() as c:
            c.cookies.set(CSRF_COOKIE_NAME, "tok-abc")
            r = await c.post("/x", headers={CSRF_HEADER_NAME: "tok-xyz"})
        assert r.status_code == 403
        assert "csrf" in r.json()["detail"].lower()


class TestHappyPath:
    async def test_matching_cookie_and_header_passes(self) -> None:
        async with await _new_client() as c:
            c.cookies.set(CSRF_COOKIE_NAME, "tok-equal")
            r = await c.post("/x", headers={CSRF_HEADER_NAME: "tok-equal"})
        assert r.status_code == 200
        assert r.json() == {"ok": "post"}

    async def test_header_name_is_case_insensitive(self) -> None:
        async with await _new_client() as c:
            c.cookies.set(CSRF_COOKIE_NAME, "tok-equal")
            r = await c.post("/x", headers={"X-CSRF-TOKEN": "tok-equal"})
        assert r.status_code == 200
