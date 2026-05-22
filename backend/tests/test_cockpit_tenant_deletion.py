"""Tests for cockpit tenant deletion (``DELETE /cockpit/tenants/{id}``).

Covers the happy path (founder + correct slug + reason), idempotent 404 on
re-delete, slug mismatch 422, and the non-founder 403 guard. Also asserts
that a system-level ``AuditLog`` row is left behind with per-table row
counts (SOC 2 evidence trail).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.db as app_db
from app.models import AuditLog, Supplier, Tenant, TenantUser, User
from tests.conftest_helpers import FounderHandle

pytestmark = pytest.mark.asyncio


async def _seed_tenant_with_supplier(slug: str = "acme") -> str:
    async with app_db.AsyncSessionLocal() as session:
        tenant = Tenant(name="Acme MGA", slug=slug)
        session.add(tenant)
        await session.flush()
        user = User(
            email=f"{slug}@example.com",
            hashed_password="x" * 60,
            full_name="Owner",
        )
        session.add(user)
        await session.flush()
        session.add(TenantUser(tenant_id=tenant.id, user_id=user.id, role="owner"))
        session.add(
            Supplier(
                tenant_id=tenant.id,
                legal_name="Vendor One",
                dba_name=None,
            )
        )
        await session.commit()
        return tenant.id


async def test_delete_tenant_happy_path(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id = await _seed_tenant_with_supplier("acme")

    res = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=founder_operator.headers,
        json={
            "reason": "Customer offboarded per signed termination notice 2026-Q1.",
            "confirm_tenant_slug": "acme",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tenant_id"] == tenant_id
    assert body["tenant_slug"] == "acme"
    assert body["row_counts"]["suppliers"] == 1
    assert body["row_counts"]["tenant_users"] == 1

    # Tenant is gone.
    async with app_db.AsyncSessionLocal() as session:
        gone = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        assert gone is None

        # System-level audit row survives.
        audit = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.action == "tenant.deleted")
                .where(AuditLog.resource_id == tenant_id)
            )
        ).scalar_one()
        assert audit.tenant_id is None
        assert audit.metadata_json["tenant_slug"] == "acme"
        assert audit.metadata_json["operator_id"] == founder_operator.operator_id
        assert audit.metadata_json["row_counts"]["suppliers"] == 1


async def test_delete_tenant_idempotent_second_call_404(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id = await _seed_tenant_with_supplier("acme")
    payload = {
        "reason": "Customer offboarded per signed notice 2026-Q1.",
        "confirm_tenant_slug": "acme",
    }
    first = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=founder_operator.headers,
        json=payload,
    )
    assert first.status_code == 200
    second = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=founder_operator.headers,
        json=payload,
    )
    assert second.status_code == 404
    assert second.json()["detail"]["code"] == "tenant_not_found"


async def test_delete_tenant_slug_mismatch_422(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id = await _seed_tenant_with_supplier("acme")
    res = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=founder_operator.headers,
        json={
            "reason": "Customer offboarded per signed notice 2026-Q1.",
            "confirm_tenant_slug": "wrong-slug",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "slug_mismatch"


async def test_delete_tenant_non_founder_forbidden(
    cockpit_client: AsyncClient, support_operator: FounderHandle
) -> None:
    tenant_id = await _seed_tenant_with_supplier("acme")
    res = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=support_operator.headers,
        json={
            "reason": "Customer offboarded per signed notice 2026-Q1.",
            "confirm_tenant_slug": "acme",
        },
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "founder_required"


async def test_delete_tenant_requires_reason_min_length(
    cockpit_client: AsyncClient, founder_operator: FounderHandle
) -> None:
    tenant_id = await _seed_tenant_with_supplier("acme")
    res = await cockpit_client.request(
        "DELETE",
        f"/cockpit/tenants/{tenant_id}",
        headers=founder_operator.headers,
        json={"reason": "nope", "confirm_tenant_slug": "acme"},
    )
    # Pydantic validation — reason has min_length=10.
    assert res.status_code == 422


async def test_delete_tenant_requires_auth(cockpit_client: AsyncClient) -> None:
    # Auth check fires before any DB lookup, so a hardcoded UUID is fine.
    res = await cockpit_client.request(
        "DELETE",
        "/cockpit/tenants/00000000-0000-0000-0000-000000000000",
        json={
            "reason": "Customer offboarded per signed notice 2026-Q1.",
            "confirm_tenant_slug": "acme",
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "operator_unauthenticated"
