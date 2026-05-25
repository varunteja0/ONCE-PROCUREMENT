"""Tests for the OperatorActAsMiddleware act-as flow."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.db as app_db
from app.api.cockpit.router import cockpit_router
from app.config import settings
from app.middleware.operator_act_as import OperatorActAsMiddleware
from app.models import (
    Operator,
    OperatorRole,
    OperatorStatus,
    OperatorTenantGrant,
    Supplier,
    Tenant,
)
from app.services import operator_auth
from app.utils.account_lockout import reset_default_tracker

pytestmark = pytest.mark.asyncio


STRONG_PWD = "C0ckpit-Act-As-T3st!2026"


@pytest_asyncio.fixture
async def cockpit_app(_test_engine, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "cockpit_jwt_secret_key", "test-cockpit-secret-" + "k" * 32)
    monkeypatch.setenv("ACCOUNT_LOCKOUT_MAX_FAILS", "50")
    reset_default_tracker()
    app = FastAPI(title="cockpit-actas-test")
    app.add_middleware(OperatorActAsMiddleware)
    app.include_router(cockpit_router)
    return app


@pytest_asyncio.fixture
async def cockpit_client(cockpit_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=cockpit_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _seed(
    *,
    operator_email: str = "founder@once.dev",
    operator_role: str = OperatorRole.FOUNDER.value,
    operator_status: str = OperatorStatus.ACTIVE.value,
    tenants: list[tuple[str, bool]] | None = None,
    grants: list[str] | None = None,
    suppliers: list[tuple[str, str]] | None = None,
) -> dict[str, str]:
    """Seed an operator + tenants + optional grants/suppliers. Returns ids."""

    if tenants is None:
        tenants = [("Acme MGA", True), ("Beta MGA", True)]
    out: dict[str, str] = {}
    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email=operator_email,
            hashed_password=operator_auth.operator_password_hash(STRONG_PWD),
            role=operator_role,
            status=operator_status,
        )
        session.add(op)
        await session.flush()
        out["operator_id"] = op.id

        for i, (name, active) in enumerate(tenants):
            t = Tenant(name=name, slug=f"tenant-{i}-{name.lower().replace(' ', '-')}", plan="pilot", is_active=active)
            session.add(t)
            await session.flush()
            out[f"tenant_{i}"] = t.id

        if grants:
            for tid in grants:
                session.add(OperatorTenantGrant(operator_id=op.id, tenant_id=tid, permission="write"))

        if suppliers:
            for tid, sname in suppliers:
                session.add(Supplier(tenant_id=tid, legal_name=sname))
        await session.commit()
    return out


async def _login(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/cockpit/auth/login",
        json={"email": email, "password": STRONG_PWD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Missing token -> 401
# ---------------------------------------------------------------------------


async def test_missing_token_returns_401(cockpit_client: AsyncClient) -> None:
    ids = await _seed()
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_0']}/suppliers",
        headers={"X-Operator-Acting-Tenant": ids["tenant_0"]},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "operator_unauthenticated"


# ---------------------------------------------------------------------------
# 2. Invalid token -> 401
# ---------------------------------------------------------------------------


async def test_invalid_token_returns_401(cockpit_client: AsyncClient) -> None:
    ids = await _seed()
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_0']}/suppliers",
        headers={
            "Authorization": "Bearer not.a.real.token",
            "X-Operator-Acting-Tenant": ids["tenant_0"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_token"


# ---------------------------------------------------------------------------
# 3. Founder bypass: can act-as any tenant without explicit grant
# ---------------------------------------------------------------------------


async def test_founder_bypass_grants(cockpit_client: AsyncClient) -> None:
    ids = await _seed(
        suppliers=[("Acme MGA-id", "ACME LLC"), ("Beta MGA-id", "Beta LLC")],
    )
    # Suppliers were created against names — fix to actual tenant ids
    async with app_db.AsyncSessionLocal() as session:
        session.add(Supplier(tenant_id=ids["tenant_0"], legal_name="Founder Bypass Supplier"))
        await session.commit()

    access = await _login(cockpit_client, "founder@once.dev")
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_0']}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": ids["tenant_0"],
        },
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert any(r["legal_name"] == "Founder Bypass Supplier" for r in rows)


# ---------------------------------------------------------------------------
# 4. Non-founder without grant -> 403 act_as_forbidden
# ---------------------------------------------------------------------------


async def test_non_founder_without_grant_forbidden(cockpit_client: AsyncClient) -> None:
    ids = await _seed(
        operator_email="support@once.dev",
        operator_role=OperatorRole.SUPPORT.value,
    )
    access = await _login(cockpit_client, "support@once.dev")
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_0']}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": ids["tenant_0"],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "act_as_forbidden"


# ---------------------------------------------------------------------------
# 5. Non-founder WITH grant can act-as that tenant
# ---------------------------------------------------------------------------


async def test_non_founder_with_grant_can_act_as(cockpit_client: AsyncClient) -> None:
    seed = await _seed(
        operator_email="support@once.dev",
        operator_role=OperatorRole.SUPPORT.value,
    )
    # Insert grant
    async with app_db.AsyncSessionLocal() as session:
        session.add(
            OperatorTenantGrant(
                operator_id=seed["operator_id"],
                tenant_id=seed["tenant_0"],
                permission="write",
            )
        )
        session.add(Supplier(tenant_id=seed["tenant_0"], legal_name="Granted Supplier"))
        session.add(Supplier(tenant_id=seed["tenant_1"], legal_name="Other Supplier"))
        await session.commit()

    access = await _login(cockpit_client, "support@once.dev")
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{seed['tenant_0']}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": seed["tenant_0"],
        },
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    names = {r["legal_name"] for r in rows}
    assert "Granted Supplier" in names
    assert "Other Supplier" not in names  # tenant scope respected


# ---------------------------------------------------------------------------
# 6. tenant_inactive -> 403
# ---------------------------------------------------------------------------


async def test_inactive_tenant_blocks_act_as(cockpit_client: AsyncClient) -> None:
    ids = await _seed(tenants=[("Acme MGA", True), ("Inactive Co", False)])
    access = await _login(cockpit_client, "founder@once.dev")
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_1']}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": ids["tenant_1"],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "tenant_inactive"


# ---------------------------------------------------------------------------
# 7. Suspended operator -> 403 operator_suspended (token issued earlier, then suspended)
# ---------------------------------------------------------------------------


async def test_suspended_operator_blocked_by_dep(cockpit_client: AsyncClient) -> None:
    await _seed()
    access = await _login(cockpit_client, "founder@once.dev")
    # Suspend after issuing the token
    async with app_db.AsyncSessionLocal() as session:
        from sqlalchemy import update

        await session.execute(
            update(Operator).where(Operator.email == "founder@once.dev").values(status=OperatorStatus.SUSPENDED.value)
        )
        await session.commit()

    resp = await cockpit_client.get(
        "/cockpit/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "operator_suspended"


# ---------------------------------------------------------------------------
# 8. Unknown tenant -> 404
# ---------------------------------------------------------------------------


async def test_unknown_tenant_returns_404(cockpit_client: AsyncClient) -> None:
    await _seed()
    access = await _login(cockpit_client, "founder@once.dev")
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{bogus}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": bogus,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] in {"tenant_not_found"}


# ---------------------------------------------------------------------------
# 9. Path/header mismatch -> 400
# ---------------------------------------------------------------------------


async def test_path_header_mismatch_returns_400(cockpit_client: AsyncClient) -> None:
    ids = await _seed()
    access = await _login(cockpit_client, "founder@once.dev")
    resp = await cockpit_client.get(
        f"/cockpit/tenants/{ids['tenant_0']}/suppliers",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Operator-Acting-Tenant": ids["tenant_1"],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "act_as_mismatch"


# ---------------------------------------------------------------------------
# 10. list_tenants returns only accessible tenants (non-founder)
# ---------------------------------------------------------------------------


async def test_list_tenants_scoped_to_grants(cockpit_client: AsyncClient) -> None:
    seed = await _seed(
        operator_email="support@once.dev",
        operator_role=OperatorRole.SUPPORT.value,
    )
    async with app_db.AsyncSessionLocal() as session:
        session.add(
            OperatorTenantGrant(
                operator_id=seed["operator_id"],
                tenant_id=seed["tenant_0"],
                permission="write",
            )
        )
        await session.commit()
    access = await _login(cockpit_client, "support@once.dev")
    resp = await cockpit_client.get("/cockpit/tenants", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seed["tenant_0"]


# ---------------------------------------------------------------------------
# 11. act-as endpoint returns permission for founder
# ---------------------------------------------------------------------------


async def test_act_as_endpoint_returns_permission(cockpit_client: AsyncClient) -> None:
    ids = await _seed()
    access = await _login(cockpit_client, "founder@once.dev")
    resp = await cockpit_client.post(
        "/cockpit/tenants/act-as",
        headers={"Authorization": f"Bearer {access}"},
        json={"tenant_id": ids["tenant_0"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["permission"] == "write"
