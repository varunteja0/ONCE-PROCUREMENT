"""Tests for cockpit audit writes + redaction."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.db as app_db
from app.api.cockpit.router import cockpit_router
from app.config import settings
from app.middleware.operator_act_as import OperatorActAsMiddleware
from app.models import CockpitAudit, Operator, OperatorRole
from app.services import operator_auth
from app.services.cockpit_audit import REDACTED, redact_payload, write_audit
from app.utils.account_lockout import reset_default_tracker

_PYTESTMARK_ASYNCIO = pytest.mark.asyncio


STRONG_PWD = "C0ckpit-Audit-T3st!2026"


@pytest_asyncio.fixture
async def cockpit_app(_test_engine, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "cockpit_jwt_secret_key", "test-cockpit-secret-" + "a" * 32)
    monkeypatch.setenv("ACCOUNT_LOCKOUT_MAX_FAILS", "50")
    reset_default_tracker()
    app = FastAPI(title="cockpit-audit-test")
    app.add_middleware(OperatorActAsMiddleware)
    app.include_router(cockpit_router)
    return app


@pytest_asyncio.fixture
async def cockpit_client(cockpit_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=cockpit_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _seed_founder(email: str = "founder@once.dev") -> str:
    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email=email,
            hashed_password=operator_auth.operator_password_hash(STRONG_PWD),
            role=OperatorRole.FOUNDER.value,
        )
        session.add(op)
        await session.commit()
        return op.id


# ---------------------------------------------------------------------------
# 1. redact_payload on flat dict
# ---------------------------------------------------------------------------


def test_redact_payload_flat() -> None:
    out = redact_payload({"email": "x@y.com", "password": "hunter2", "Authorization": "Bearer xyz"})
    assert out is not None
    assert out["email"] == "x@y.com"
    assert out["password"] == REDACTED
    assert out["Authorization"] == REDACTED


# ---------------------------------------------------------------------------
# 2. redact_payload on nested dict
# ---------------------------------------------------------------------------


def test_redact_payload_nested() -> None:
    out = redact_payload(
        {
            "headers": {
                "Cookie": "session=abc",
                "User-Agent": "pytest",
            },
            "body": {"refresh_token": "rt"},
        }
    )
    assert out is not None
    assert out["headers"]["Cookie"] == REDACTED
    assert out["headers"]["User-Agent"] == "pytest"
    assert out["body"]["refresh_token"] == REDACTED


# ---------------------------------------------------------------------------
# 3. redact_payload on list-of-dicts
# ---------------------------------------------------------------------------


def test_redact_payload_list_of_dicts() -> None:
    out = redact_payload({"items": [{"password": "1"}, {"name": "ok"}]})
    assert out is not None
    assert out["items"][0]["password"] == REDACTED
    assert out["items"][1]["name"] == "ok"


# ---------------------------------------------------------------------------
# 4. redact_payload returns None for None input
# ---------------------------------------------------------------------------


def test_redact_payload_none() -> None:
    assert redact_payload(None) is None


# ---------------------------------------------------------------------------
# 5. Every cockpit-routed request produces an audit row
# ---------------------------------------------------------------------------


@_PYTESTMARK_ASYNCIO
async def test_cockpit_request_creates_audit_row(cockpit_client: AsyncClient) -> None:
    await _seed_founder()
    login = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "founder@once.dev", "password": STRONG_PWD},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]

    me = await cockpit_client.get(
        "/cockpit/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert me.status_code == 200

    # Allow the fire-and-forget audit writer to settle.
    async with app_db.AsyncSessionLocal() as session:
        rows = (await session.execute(select(CockpitAudit).order_by(CockpitAudit.occurred_at))).scalars().all()
    paths = [r.path for r in rows]
    assert any(p and p.endswith("/cockpit/auth/login") for p in paths)
    assert any(p and p.endswith("/cockpit/auth/me") for p in paths)


# ---------------------------------------------------------------------------
# 6. write_audit redacts authorization in stored payload
# ---------------------------------------------------------------------------


@_PYTESTMARK_ASYNCIO
async def test_write_audit_redacts_sensitive(async_session) -> None:
    await write_audit(
        async_session,
        operator_id=None,
        tenant_id_acted_as=None,
        action="cockpit.test",
        resource_type="test",
        payload={"Authorization": "Bearer secret", "ok": True},
    )
    await async_session.commit()
    rows = (await async_session.execute(select(CockpitAudit))).scalars().all()
    assert rows
    stored = rows[-1].payload_redacted
    assert stored is not None
    assert stored["Authorization"] == REDACTED
    assert stored["ok"] is True


# ---------------------------------------------------------------------------
# 7. List endpoint requires operator auth
# ---------------------------------------------------------------------------


@_PYTESTMARK_ASYNCIO
async def test_audit_list_requires_operator(cockpit_client: AsyncClient) -> None:
    resp = await cockpit_client.get("/cockpit/audit")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 8. List endpoint filters by operator_id
# ---------------------------------------------------------------------------


@_PYTESTMARK_ASYNCIO
async def test_audit_list_filters_by_operator(cockpit_client: AsyncClient) -> None:
    op_id = await _seed_founder()
    login = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "founder@once.dev", "password": STRONG_PWD},
    )
    access = login.json()["access_token"]
    # generate some rows
    await cockpit_client.get("/cockpit/auth/me", headers={"Authorization": f"Bearer {access}"})
    resp = await cockpit_client.get(
        "/cockpit/audit",
        params={"operator_id": op_id},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items
    assert all(it["operator_id"] == op_id for it in items)
