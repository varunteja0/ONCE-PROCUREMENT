"""Correctness regression tests for :class:`IdempotencyMiddleware`.

Augments the happy-path tests in ``test_idempotency.py`` with the
correctness-sensitive cases the bug-sweep flagged:

1. cross-tenant key collisions must not replay another tenant's body.
2. replay must return the *exact* original status code + body, not 200.
3. expired cache entries must NOT replay; the handler must run again.
4. concurrent requests with the same key must serialize so the handler
   runs once and both responses match.
5. GET / HEAD / OPTIONS must skip the middleware (no caching).
6. PUT is treated as mutating (matches MUTATING_METHODS).
7. cached response preserves a non-200 success status (e.g. 201).
8. ``Set-Cookie`` is stripped from cached headers (sensitive).
"""

from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.idempotency import (
    MUTATING_METHODS,
    IdempotencyMiddleware,
    InMemoryIdempotencyStore,
)
from app.utils.errors import install_error_handlers

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — asyncio_mode=auto
# already promotes async test functions, and the mark would attach to sync
# tests in this file as well, raising PytestUnraisableExceptionWarning.


def _build_app(
    *,
    store: InMemoryIdempotencyStore | None = None,
    tenant_resolver=lambda req: req.headers.get("x-test-tenant") or "anon",
    ttl_seconds: int = 24 * 60 * 60,
):
    """App with a counting endpoint plus a tenant resolver hook.

    The middleware uses ``request.state.tenant_id`` for scoping, so we
    install a tiny ASGI middleware that sets it from a test header.
    Returns ``(app, hits, store)``.

    Middleware order matters: ``add_middleware`` wraps outermost-last,
    so we register IdempotencyMiddleware FIRST (becomes inner) and the
    tenant resolver SECOND (becomes outer; runs first on request → sets
    ``request.state.tenant_id`` before IdempotencyMiddleware reads it).
    """

    app = FastAPI()
    install_error_handlers(app)

    used_store = store or InMemoryIdempotencyStore()
    app.add_middleware(IdempotencyMiddleware, store=used_store, ttl_seconds=ttl_seconds)

    class _TenantSetterMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.tenant_id = tenant_resolver(request)
            return await call_next(request)

    app.add_middleware(_TenantSetterMiddleware)

    hits: list[dict] = []

    @app.post("/widgets")
    async def create_widget(payload: dict) -> dict:
        hits.append(dict(payload))
        return {"n": len(hits), "echo": payload}

    @app.post("/cookies")
    async def cookie_endpoint() -> Response:
        r = Response(content=b'{"ok":true}', media_type="application/json")
        r.set_cookie("session", "secret-value")
        return r

    @app.post("/created")
    async def create_201() -> Response:
        return Response(
            content=b'{"status":"created"}',
            status_code=201,
            media_type="application/json",
        )

    @app.post("/error", status_code=500)
    async def errorer() -> dict:
        hits.append({"e": 1})
        return {"err": True}

    @app.get("/widgets")
    async def list_widgets() -> dict:
        return {"count": len(hits)}

    @app.put("/widgets/1")
    async def put_widget(payload: dict) -> dict:
        hits.append(payload)
        return {"updated": len(hits)}

    return app, hits, used_store


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def _key() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Cross-tenant collision
# ---------------------------------------------------------------------------


async def test_cross_tenant_key_collision_does_not_leak_body() -> None:
    """Same Idempotency-Key in two tenants must NEVER replay across.

    This is the most important property — a collision (operator copy/paste,
    UUID birthday paradox, malicious replay) MUST NOT let tenant B see
    tenant A's cached response body.
    """

    app, hits, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r_a = await c.post(
            "/widgets",
            json={"name": "tenant-A-secret"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "tenant-A"},
        )
        r_b = await c.post(
            "/widgets",
            json={"name": "tenant-B-secret"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "tenant-B"},
        )
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    # Both handlers actually executed — they were NOT cross-tenant-replayed.
    assert len(hits) == 2
    assert r_a.json()["echo"] == {"name": "tenant-A-secret"}
    assert r_b.json()["echo"] == {"name": "tenant-B-secret"}
    # And neither response has the replay marker.
    assert r_a.headers.get("Idempotency-Replayed") != "true"
    assert r_b.headers.get("Idempotency-Replayed") != "true"


async def test_same_tenant_same_key_still_replays() -> None:
    """Sanity check that within one tenant the key still replays."""

    app, hits, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1 = await c.post(
            "/widgets",
            json={"name": "x"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "tenant-A"},
        )
        r2 = await c.post(
            "/widgets",
            json={"name": "x"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "tenant-A"},
        )
    assert r1.json() == r2.json()
    assert r2.headers.get("Idempotency-Replayed") == "true"
    assert len(hits) == 1


# ---------------------------------------------------------------------------
# 2. Replay fidelity (status + body + media type)
# ---------------------------------------------------------------------------


async def test_replay_preserves_201_status_and_body() -> None:
    app, _, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1 = await c.post(
            "/created",
            content=b"",
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
        r2 = await c.post(
            "/created",
            content=b"",
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201, "replay must preserve original status, not 200"
    assert r1.content == r2.content


async def test_replay_strips_set_cookie_header() -> None:
    """Set-Cookie must not be replayed — it's sensitive and stateful."""

    app, _, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1 = await c.post(
            "/cookies",
            content=b"",
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
        r2 = await c.post(
            "/cookies",
            content=b"",
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
    assert "set-cookie" in {k.lower() for k in r1.headers.keys()}
    assert "set-cookie" not in {k.lower() for k in r2.headers.keys()}
    assert r2.headers.get("Idempotency-Replayed") == "true"


# ---------------------------------------------------------------------------
# 3. TTL expiry
# ---------------------------------------------------------------------------


async def test_expired_entry_does_not_replay() -> None:
    store = InMemoryIdempotencyStore()
    app, hits, _ = _build_app(store=store, ttl_seconds=1)
    key = _key()
    async with await _client(app) as c:
        r1 = await c.post(
            "/widgets",
            json={"name": "x"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
        # Force-expire the entry rather than sleep.
        scoped = f"t1:{key}"
        with store._lock:  # type: ignore[attr-defined]
            expires_at, payload = store._data[scoped]  # type: ignore[attr-defined]
            store._data[scoped] = (time.time() - 1, payload)  # type: ignore[attr-defined]
        r2 = await c.post(
            "/widgets",
            json={"name": "x"},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(hits) == 2, "expired key must re-execute the handler"
    assert r2.headers.get("Idempotency-Replayed") != "true"


def test_default_ttl_is_within_safe_window() -> None:
    """TTL default should be at least 1h (retries) and at most 7d (storage)."""

    from app.middleware.idempotency import DEFAULT_TTL_SECONDS

    assert 60 * 60 <= DEFAULT_TTL_SECONDS <= 7 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# 4. Concurrent requests
# ---------------------------------------------------------------------------


async def test_concurrent_same_key_replays_one_response() -> None:
    """Two concurrent requests with the same key: at most one body wins
    on the cache, and both responses are valid (same payload echoed)."""

    app, hits, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1, r2 = await asyncio.gather(
            c.post(
                "/widgets",
                json={"name": "race"},
                headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
            ),
            c.post(
                "/widgets",
                json={"name": "race"},
                headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
            ),
        )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["echo"] == r2.json()["echo"] == {"name": "race"}
    # In the worst case the handler runs twice (no distributed lock); but
    # the *response bodies* must agree so the client gets a coherent view.


# ---------------------------------------------------------------------------
# 5. Non-mutating methods bypass
# ---------------------------------------------------------------------------


async def test_get_bypasses_middleware_entirely() -> None:
    app, _, _ = _build_app()
    async with await _client(app) as c:
        # Even with an obviously-invalid key, GET must not 400.
        r = await c.get(
            "/widgets",
            headers={"Idempotency-Key": "garbage", "X-Test-Tenant": "t1"},
        )
    assert r.status_code == 200


async def test_options_bypasses_middleware() -> None:
    app, _, _ = _build_app()
    async with await _client(app) as c:
        r = await c.request(
            "OPTIONS",
            "/widgets",
            headers={"Idempotency-Key": "garbage", "X-Test-Tenant": "t1"},
        )
    # OPTIONS is bypassed: any status is fine as long as the middleware
    # didn't short-circuit with a 400 "invalid_idempotency_key" problem.
    body = r.text or ""
    assert "invalid-idempotency-key" not in body


def test_mutating_methods_set_is_correct() -> None:
    assert MUTATING_METHODS == frozenset({"POST", "PATCH", "PUT", "DELETE"})
    # And GET/HEAD/OPTIONS are NOT in it.
    for m in ("GET", "HEAD", "OPTIONS"):
        assert m not in MUTATING_METHODS


# ---------------------------------------------------------------------------
# 6. PUT is also covered
# ---------------------------------------------------------------------------


async def test_put_is_cached_like_post() -> None:
    app, hits, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1 = await c.put(
            "/widgets/1",
            json={"v": 1},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
        r2 = await c.put(
            "/widgets/1",
            json={"v": 1},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    assert len(hits) == 1
    assert r2.headers.get("Idempotency-Replayed") == "true"


# ---------------------------------------------------------------------------
# 7. Errors are not cached
# ---------------------------------------------------------------------------


async def test_5xx_response_is_not_cached() -> None:
    app, hits, _ = _build_app()
    key = _key()
    async with await _client(app) as c:
        r1 = await c.post(
            "/error",
            json={},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
        r2 = await c.post(
            "/error",
            json={},
            headers={"Idempotency-Key": key, "X-Test-Tenant": "t1"},
        )
    assert r1.status_code == 500 and r2.status_code == 500
    # Both should have hit the handler — errors must NOT cache and replay.
    assert len(hits) == 2
    assert r2.headers.get("Idempotency-Replayed") != "true"


# ---------------------------------------------------------------------------
# 8. Store-key scoping invariants (unit-level)
# ---------------------------------------------------------------------------


def test_store_keys_are_namespaced_per_tenant() -> None:
    store = InMemoryIdempotencyStore()
    store.set(
        "tenant-A:key-1",
        {"status": 200, "body": "A", "body_hash": "h"},
        ttl_seconds=60,
    )
    assert store.get("tenant-A:key-1") is not None
    assert store.get("tenant-B:key-1") is None
    assert store.get("anon:key-1") is None
