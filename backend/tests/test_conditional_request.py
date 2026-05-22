"""Tests for the conditional-request middleware + ETag helpers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.conditional_request import ConditionalRequestMiddleware
from app.utils.errors import install_error_handlers
from app.utils.etag import (
    check_if_match,
    compute_strong_etag,
    compute_weak_etag,
    etag_matches,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(ConditionalRequestMiddleware)

    @app.get("/widgets/1")
    async def widget() -> dict[str, str]:
        return {"id": "1", "name": "alpha"}

    @app.get("/widgets/2")
    async def widget_with_explicit_etag() -> dict[str, str]:
        from fastapi.responses import JSONResponse

        return JSONResponse({"id": "2"}, headers={"ETag": 'W/"deadbeef"'})

    @app.patch("/widgets/1")
    async def patch_widget(request: Request) -> dict[str, str]:
        # Resource currently has strong etag "v1".
        check_if_match(request, current_etag='"v1"')
        return {"id": "1", "name": "updated"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


class TestEtagComputation:
    def test_weak_etag_format(self) -> None:
        et = compute_weak_etag(b"hello")
        assert et.startswith('W/"')
        assert et.endswith('"')

    def test_weak_etag_is_deterministic(self) -> None:
        assert compute_weak_etag(b"hello") == compute_weak_etag(b"hello")

    def test_weak_etag_differs_for_different_bodies(self) -> None:
        assert compute_weak_etag(b"a") != compute_weak_etag(b"b")

    def test_strong_etag_format(self) -> None:
        et = compute_strong_etag("row-1", "2025-01-01T00:00:00Z")
        assert et.startswith('"')
        assert not et.startswith('W/"')

    def test_etag_matches_weak_strong_pair(self) -> None:
        # Weak comparison: ignore the W/ prefix.
        assert etag_matches('W/"abc"', '"abc"')
        assert not etag_matches('W/"abc"', '"xyz"')

    def test_wildcard_matches_anything(self) -> None:
        assert etag_matches("*", 'W/"anything"')


class TestConditionalGet:
    async def test_etag_is_added_to_response(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/widgets/1")
        assert r.status_code == 200
        assert r.headers.get("ETag", "").startswith('W/"')

    async def test_if_none_match_returns_304(self) -> None:
        async with await _client(_build_app()) as c:
            r1 = await c.get("/widgets/1")
            etag = r1.headers["ETag"]
            r2 = await c.get("/widgets/1", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("ETag") == etag

    async def test_if_none_match_wildcard_returns_304(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/widgets/1", headers={"If-None-Match": "*"})
        assert r.status_code == 304

    async def test_if_none_match_mismatch_returns_full_body(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/widgets/1", headers={"If-None-Match": 'W/"not-the-tag"'})
        assert r.status_code == 200
        assert r.json() == {"id": "1", "name": "alpha"}

    async def test_existing_etag_is_preserved(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/widgets/2")
        assert r.headers["ETag"] == 'W/"deadbeef"'

    async def test_health_is_excluded(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.get("/health")
        assert r.status_code == 200
        # Excluded path: no ETag computation.
        assert "etag" not in {k.lower() for k in r.headers}


class TestIfMatch:
    async def test_no_header_proceeds(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.patch("/widgets/1", json={})
        assert r.status_code == 200

    async def test_matching_if_match_proceeds(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.patch("/widgets/1", json={}, headers={"If-Match": '"v1"'})
        assert r.status_code == 200

    async def test_mismatched_if_match_returns_412(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.patch("/widgets/1", json={}, headers={"If-Match": '"v2"'})
        assert r.status_code == 412
        assert r.json()["type"].endswith("/precondition-failed")

    async def test_wildcard_if_match_with_existing_resource(self) -> None:
        async with await _client(_build_app()) as c:
            r = await c.patch("/widgets/1", json={}, headers={"If-Match": "*"})
        assert r.status_code == 200
