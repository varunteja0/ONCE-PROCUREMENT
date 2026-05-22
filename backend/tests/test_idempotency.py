"""Tests for the Idempotency-Key middleware."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.idempotency import (
    IdempotencyMiddleware,
    InMemoryIdempotencyStore,
)
from app.utils.errors import install_error_handlers

pytestmark = pytest.mark.asyncio


def _build_app(
    *,
    store: InMemoryIdempotencyStore | None = None,
    required_path_prefixes: tuple[str, ...] = (),
) -> tuple[FastAPI, list[int]]:
    """Build an app with a counting create endpoint.

    Returns (app, hits) — the list tracks how many times the underlying
    handler actually executed, so we can assert cache hits skip it.
    """

    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(
        IdempotencyMiddleware,
        store=store or InMemoryIdempotencyStore(),
        required_path_prefixes=required_path_prefixes,
    )

    hits: list[int] = []
    counter = {"n": 0}

    @app.post("/widgets")
    async def create_widget(payload: dict) -> dict:
        counter["n"] += 1
        hits.append(counter["n"])
        return {"created": counter["n"], "echo": payload.get("name", "")}

    @app.get("/widgets")
    async def list_widgets() -> dict[str, list[int]]:
        return {"items": hits}

    @app.post("/v1/auth/login")
    async def fake_login() -> dict[str, str]:
        counter["n"] += 1
        return {"token": f"t-{counter['n']}"}

    return app, hits


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _key() -> str:
    return str(uuid.uuid4())


class TestPassthrough:
    async def test_get_is_passthrough(self) -> None:
        app, _ = _build_app()
        async with await _client(app) as c:
            r = await c.get("/widgets")
        assert r.status_code == 200

    async def test_post_without_key_is_processed_normally(self) -> None:
        app, hits = _build_app()
        async with await _client(app) as c:
            r1 = await c.post("/widgets", json={"name": "a"})
            r2 = await c.post("/widgets", json={"name": "a"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Both requests hit the handler — no caching without a key.
        assert len(hits) == 2


class TestReplay:
    async def test_same_key_same_body_returns_cached_response(self) -> None:
        app, hits = _build_app()
        key = _key()
        async with await _client(app) as c:
            r1 = await c.post("/widgets", json={"name": "a"}, headers={"Idempotency-Key": key})
            r2 = await c.post("/widgets", json={"name": "a"}, headers={"Idempotency-Key": key})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == r2.json()
        # Replay headed back with the marker.
        assert r2.headers.get("Idempotency-Replayed") == "true"
        # Handler ran exactly once.
        assert len(hits) == 1

    async def test_same_key_different_body_returns_422_conflict(self) -> None:
        app, hits = _build_app()
        key = _key()
        async with await _client(app) as c:
            r1 = await c.post("/widgets", json={"name": "a"}, headers={"Idempotency-Key": key})
            r2 = await c.post("/widgets", json={"name": "b"}, headers={"Idempotency-Key": key})
        assert r1.status_code == 200
        assert r2.status_code == 422
        body = r2.json()
        assert body["type"].endswith("/idempotency-key-conflict")
        # Only the first request hit the handler.
        assert len(hits) == 1


class TestKeyValidation:
    async def test_invalid_key_returns_400(self) -> None:
        app, _ = _build_app()
        async with await _client(app) as c:
            r = await c.post(
                "/widgets",
                json={"name": "x"},
                headers={"Idempotency-Key": "not-a-uuid-or-ulid"},
            )
        assert r.status_code == 400
        assert r.json()["type"].endswith("/invalid-idempotency-key")

    async def test_ulid_format_is_accepted(self) -> None:
        app, _ = _build_app()
        async with await _client(app) as c:
            r = await c.post(
                "/widgets",
                json={"name": "x"},
                headers={"Idempotency-Key": "01HXY3QF6ABCDEFGHJKMNPQRST"},
            )
        assert r.status_code == 200


class TestRequiredPaths:
    async def test_missing_key_on_required_path_returns_400(self) -> None:
        app, _ = _build_app(required_path_prefixes=("/widgets",))
        async with await _client(app) as c:
            r = await c.post("/widgets", json={"name": "x"})
        assert r.status_code == 400
        assert r.json()["type"].endswith("/idempotency-key-required")


class TestExcludedPaths:
    async def test_auth_login_is_excluded(self) -> None:
        app, _ = _build_app()
        async with await _client(app) as c:
            # No idempotency key, no header check — auth is bypassed.
            r1 = await c.post("/v1/auth/login")
            r2 = await c.post("/v1/auth/login")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() != r2.json()


class TestStoreSharing:
    async def test_store_keys_are_tenant_scoped(self) -> None:
        store = InMemoryIdempotencyStore()
        # Same scoped key reused across calls works.
        store.set("t1:abc", {"status": 200, "body": "x", "body_hash": "h"}, 60)
        assert store.get("t1:abc") is not None
        assert store.get("t2:abc") is None
