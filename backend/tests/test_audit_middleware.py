"""L3.10 — Tests for :class:`app.middleware.audit_middleware.AuditMiddleware`."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.db as app_db
from app.middleware.audit_middleware import (
    ACTION_VERBS,
    AuditMiddleware,
    extract_resource,
)
from app.models import Tenant
from app.models.audit_log import AuditActorType, AuditLogEntry

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Pure-function tests for extract_resource — no DB / no app required.
# These are async no-ops so they obey the module-level asyncio mark.
# ---------------------------------------------------------------------------


async def test_extract_resource_with_id() -> None:
    assert extract_resource("/v1/suppliers/abc-123") == ("supplier", "abc-123")


async def test_extract_resource_without_id() -> None:
    assert extract_resource("/v1/suppliers") == ("supplier", None)


async def test_extract_resource_filters_action_segments() -> None:
    for path in (
        "/v1/suppliers/new",
        "/v1/audit/chain/verify",
        "/v1/audit/exports",
        "/v1/inbound/rules",
    ):
        rt, rid = extract_resource(path)
        assert rid is None, path


async def test_extract_resource_kebab_collection() -> None:
    rt, _ = extract_resource("/v1/loss-runs/abc")
    assert rt == "loss_run"


async def test_extract_resource_unknown_collection_falls_back() -> None:
    rt, rid = extract_resource("/v1/widgets/w-1")
    assert rt == "widgets"
    assert rid == "w-1"


async def test_action_verbs_table() -> None:
    assert ACTION_VERBS["POST"] == "created"
    assert ACTION_VERBS["PUT"] == "updated"
    assert ACTION_VERBS["PATCH"] == "updated"
    assert ACTION_VERBS["DELETE"] == "deleted"
    assert "GET" not in ACTION_VERBS


# ---------------------------------------------------------------------------
# End-to-end: mount the middleware on a bare app and assert the row.
# ---------------------------------------------------------------------------


async def _seed_tenant(tid: str = "t-mw") -> None:
    async with app_db.AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name="x", slug=tid, plan="pilot", is_active=True))
        await s.commit()


def _wrap_with_state(
    app: FastAPI,
    *,
    tenant_id: str | None = "t-mw",
    user_id: str = "u-1",
    request_id: str = "req-test",
):
    """Wrap *app* with a pure-ASGI middleware that primes ``scope['state']``.

    Using a pure-ASGI wrapper (instead of ``@app.middleware('http')`` which is
    BaseHTTPMiddleware) avoids the well-known Starlette issue where state set
    in an outer BaseHTTPMiddleware is not visible to an inner one because
    each constructs its own Request object from the scope.
    """

    async def _app(scope, receive, send):  # noqa: ANN001
        if scope.get("type") == "http":
            # Starlette stores request.state values in scope["state"] as a
            # plain dict; the State wrapper is constructed lazily over it.
            state: dict = scope.setdefault("state", {})
            if not isinstance(state, dict):
                state = {}
                scope["state"] = state
            if tenant_id is not None:
                state["tenant_id"] = tenant_id
            state["user_id"] = user_id
            state["request_id"] = request_id
        await app(scope, receive, send)

    return _app


def _build_app() -> object:
    app = FastAPI()
    app.add_middleware(AuditMiddleware)

    @app.post("/v1/suppliers")
    async def create_supplier():
        return {"ok": True}

    @app.get("/v1/suppliers")
    async def list_suppliers():
        return []

    @app.delete("/v1/suppliers/abc")
    async def delete_supplier():
        return {"ok": True}

    return _wrap_with_state(app)


async def _count_rows(tid: str = "t-mw") -> int:
    async with app_db.AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(AuditLogEntry).where(AuditLogEntry.tenant_id == tid)
            )
        ).scalars().all()
        return len(rows)


async def _wait_for_rows(target: int, *, tid: str = "t-mw", timeout: float = 2.0) -> int:
    elapsed = 0.0
    while elapsed < timeout:
        n = await _count_rows(tid)
        if n >= target:
            return n
        await asyncio.sleep(0.05)
        elapsed += 0.05
    return await _count_rows(tid)


async def test_post_emits_one_audit_row(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/v1/suppliers", json={})
        assert r.status_code == 200
    n = await _wait_for_rows(1)
    assert n == 1


async def test_get_does_not_emit_audit_row(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await c.get("/v1/suppliers")
    # No POST → no row should have been written within 0.3s.
    await asyncio.sleep(0.3)
    assert await _count_rows() == 0


async def test_delete_recorded_as_deleted(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await c.delete("/v1/suppliers/abc")
    await _wait_for_rows(1)
    async with app_db.AsyncSessionLocal() as s:
        row = (
            await s.execute(select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-mw"))
        ).scalars().first()
    assert row is not None
    assert row.action_verb == "deleted"
    assert row.resource_type == "supplier"
    assert row.resource_id == "abc"


async def test_no_tenant_state_skips_audit(_test_engine) -> None:  # noqa: ANN001
    """If tenant_scope didn't set tenant_id, audit middleware must not write."""

    app = FastAPI()
    app.add_middleware(AuditMiddleware)

    @app.post("/v1/suppliers")
    async def create_supplier():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/v1/suppliers", json={})
        assert r.status_code == 200
    await asyncio.sleep(0.3)
    async with app_db.AsyncSessionLocal() as s:
        rows = (await s.execute(select(AuditLogEntry))).scalars().all()
    assert rows == []


async def test_operator_header_sets_actor_type(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await c.post(
            "/v1/suppliers",
            json={},
            headers={"X-Operator-Acting-Tenant": "yes"},
        )
    await _wait_for_rows(1)
    async with app_db.AsyncSessionLocal() as s:
        row = (
            await s.execute(select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-mw"))
        ).scalars().first()
    assert row is not None
    assert row.actor_type == AuditActorType.OPERATOR


async def test_user_actor_when_no_operator_header(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await c.post("/v1/suppliers", json={})
    await _wait_for_rows(1)
    async with app_db.AsyncSessionLocal() as s:
        row = (
            await s.execute(select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-mw"))
        ).scalars().first()
    assert row is not None
    assert row.actor_type == AuditActorType.USER


async def test_health_endpoint_is_skipped(_test_engine) -> None:  # noqa: ANN001
    await _seed_tenant()
    app = FastAPI()
    app.add_middleware(AuditMiddleware)

    @app.post("/v1/health")
    async def health():
        return {"ok": True}

    wrapped = _wrap_with_state(app)
    transport = ASGITransport(app=wrapped)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await c.post("/v1/health", json={})
    await asyncio.sleep(0.3)
    assert await _count_rows() == 0


async def test_failed_handler_still_audits_response(_test_engine) -> None:  # noqa: ANN001
    """A 500 from the handler should still emit an audit row with status_code=500."""
    await _seed_tenant()
    app = FastAPI()
    app.add_middleware(AuditMiddleware)

    @app.post("/v1/suppliers")
    async def boom():
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="x")

    wrapped = _wrap_with_state(app)
    transport = ASGITransport(app=wrapped)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/v1/suppliers", json={})
        assert r.status_code == 500
    await _wait_for_rows(1)
    async with app_db.AsyncSessionLocal() as s:
        row = (
            await s.execute(select(AuditLogEntry).where(AuditLogEntry.tenant_id == "t-mw"))
        ).scalars().first()
    assert row is not None
    assert row.payload_summary["status_code"] == 500


async def test_audit_write_failure_does_not_break_response(
    monkeypatch: pytest.MonkeyPatch, _test_engine
) -> None:  # noqa: ANN001
    await _seed_tenant()

    # Patch record_audit_event in the middleware to raise.
    async def boom(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("audit table on fire")

    monkeypatch.setattr(
        "app.middleware.audit_middleware.record_audit_event", boom
    )

    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/v1/suppliers", json={})
        assert r.status_code == 200
    await asyncio.sleep(0.2)
    # No row written, but the response succeeded.
    assert await _count_rows() == 0
