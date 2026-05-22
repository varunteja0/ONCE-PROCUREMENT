"""Endpoint tests for the /v1/consents API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.models import Tenant, User
from tests.conftest import register_user
from tests.factories import make_consent, make_portal, make_supplier

pytestmark = pytest.mark.asyncio


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _auth_context(auth_client: tuple[AsyncClient, Any], async_session) -> tuple[AsyncClient, Tenant, User]:
    client, _ = auth_client
    me = (await client.get("/v1/auth/me")).json()
    tenant = await async_session.get(Tenant, me["tenant_id"])
    user = await async_session.get(User, me["id"])
    assert tenant is not None
    assert user is not None
    return client, tenant, user


async def test_list_consents_filters_by_supplier_and_active_only(
    auth_client: tuple[AsyncClient, Any], async_session
) -> None:
    client, tenant, user = await _auth_context(auth_client, async_session)
    supplier = await make_supplier(async_session, tenant)
    other_supplier = await make_supplier(async_session, tenant, legal_name="Other LLC")
    portal = await make_portal(async_session)
    active = await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
    )
    await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
        revoked_at=datetime.now(UTC),
    )
    await make_consent(
        async_session,
        supplier=other_supplier,
        portal=portal,
        granted_by=user,
    )
    await async_session.commit()

    response = await client.get(
        "/v1/consents",
        params={"supplier_id": supplier.id, "active_only": "true", "limit": 10},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [active.id]
    assert body["items"][0]["portal_ids_json"] == [portal.id]


async def test_get_consent_by_id(auth_client: tuple[AsyncClient, Any], async_session) -> None:
    client, tenant, user = await _auth_context(auth_client, async_session)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session)
    consent = await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
    )
    await async_session.commit()

    response = await client.get(f"/v1/consents/{consent.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == consent.id
    assert body["tenant_id"] == tenant.id
    assert body["supplier_id"] == supplier.id
    assert body["signature_b64"] == consent.signature_b64


async def test_get_consent_cross_tenant_returns_404(client: AsyncClient, async_session) -> None:
    tenant_a = await register_user(
        client,
        email="consent-a@example.com",
        password="StrongPass-A1!",
        tenant_name="Consent A",
    )
    tenant_b = await register_user(
        client,
        email="consent-b@example.com",
        password="StrongPass-B2!",
        tenant_name="Consent B",
    )
    me_a = (await client.get("/v1/auth/me", headers=_bearer(tenant_a.tokens.access_token))).json()
    tenant = await async_session.get(Tenant, me_a["tenant_id"])
    user = await async_session.get(User, me_a["id"])
    assert tenant is not None
    assert user is not None
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session)
    consent = await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
    )
    await async_session.commit()

    response = await client.get(
        f"/v1/consents/{consent.id}",
        headers=_bearer(tenant_b.tokens.access_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "consent_record_not_found"


async def test_list_consents_cross_tenant_supplier_filter_returns_empty(client: AsyncClient, async_session) -> None:
    tenant_a = await register_user(
        client,
        email="consent-list-a@example.com",
        password="StrongPass-A1!",
        tenant_name="Consent List A",
    )
    tenant_b = await register_user(
        client,
        email="consent-list-b@example.com",
        password="StrongPass-B2!",
        tenant_name="Consent List B",
    )
    me_a = (await client.get("/v1/auth/me", headers=_bearer(tenant_a.tokens.access_token))).json()
    tenant = await async_session.get(Tenant, me_a["tenant_id"])
    user = await async_session.get(User, me_a["id"])
    assert tenant is not None
    assert user is not None
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session)
    await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
    )
    await async_session.commit()

    response = await client.get(
        "/v1/consents",
        params={"supplier_id": supplier.id},
        headers=_bearer(tenant_b.tokens.access_token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_consents_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/v1/consents")

    assert response.status_code == 401


async def test_list_consents_rejects_invalid_limit(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client

    response = await client.get("/v1/consents", params={"limit": 0})

    assert response.status_code == 422


async def test_list_consents_filters_by_portal_id(
    auth_client: tuple[AsyncClient, Any], async_session
) -> None:
    client, tenant, user = await _auth_context(auth_client, async_session)
    supplier = await make_supplier(async_session, tenant)
    portal_a = await make_portal(async_session)
    # Two consents — one scoped to portal_a, one wildcard.
    consent_a = await make_consent(
        async_session,
        supplier=supplier,
        portal=portal_a,
        granted_by=user,
    )
    consent_wild = await make_consent(
        async_session,
        supplier=supplier,
        granted_by=user,
    )
    # Sanity: wildcard consent stores ["*"]
    assert consent_wild.portal_ids_json == ["*"]
    await async_session.commit()

    response = await client.get(
        "/v1/consents",
        params={"supplier_id": supplier.id, "portal_id": portal_a.id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    returned = {item["id"] for item in body["items"]}
    # Both should match: portal_a explicitly + wildcard consent.
    assert consent_a.id in returned
    assert consent_wild.id in returned
    assert body["total"] == 2


async def test_list_consents_accepts_active_alias(
    auth_client: tuple[AsyncClient, Any], async_session
) -> None:
    client, tenant, user = await _auth_context(auth_client, async_session)
    supplier = await make_supplier(async_session, tenant)
    portal = await make_portal(async_session)
    active_consent = await make_consent(
        async_session, supplier=supplier, portal=portal, granted_by=user
    )
    await make_consent(
        async_session,
        supplier=supplier,
        portal=portal,
        granted_by=user,
        revoked_at=datetime.now(UTC),
    )
    await async_session.commit()

    # ``active=true`` is the alias the extension uses.
    response = await client.get(
        "/v1/consents",
        params={"supplier_id": supplier.id, "active": "true"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [active_consent.id]

    # When both ``active`` and ``active_only`` are supplied, ``active`` wins.
    conflicting = await client.get(
        "/v1/consents",
        params={
            "supplier_id": supplier.id,
            "active": "true",
            "active_only": "false",
        },
    )
    assert conflicting.status_code == 200, conflicting.text
    assert conflicting.json()["total"] == 1
