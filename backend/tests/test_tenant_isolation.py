"""Cross-tenant isolation tests for the supplier API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_SUPPLIER_PAYLOAD: dict[str, object] = {
    "legal_name": "Acme Underwriting LLC",
    "dba_name": "Acme",
    "ein": "12-3456789",
    "naics_code": "524210",
    "primary_email": "ops@acme.example",
    "primary_phone": "+1-555-555-0100",
    "website": "https://acme.example/",
}


async def _register_two_tenants(client: AsyncClient) -> tuple[str, str]:
    """Register tenants A and B; return their access tokens."""

    tenant_a = await register_user(
        client,
        email="a-owner@example.com",
        password="Sup3rSecret-A!",
        full_name="Tenant A Owner",
        tenant_name="Tenant A",
    )
    tenant_b = await register_user(
        client,
        email="b-owner@example.com",
        password="Sup3rSecret-B!",
        full_name="Tenant B Owner",
        tenant_name="Tenant B",
    )
    return tenant_a.tokens.access_token, tenant_b.tokens.access_token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier_for(
    client: AsyncClient, token: str, *, legal_name: str | None = None
) -> str:
    payload = dict(_SUPPLIER_PAYLOAD)
    if legal_name is not None:
        payload["legal_name"] = legal_name
    response = await client.post("/v1/suppliers", json=payload, headers=_bearer(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_cross_tenant_get_returns_404(client: AsyncClient) -> None:
    token_a, token_b = await _register_two_tenants(client)
    supplier_id = await _create_supplier_for(client, token_a)

    # Tenant A owns the supplier and can read it.
    own = await client.get(f"/v1/suppliers/{supplier_id}", headers=_bearer(token_a))
    assert own.status_code == 200, own.text

    # Tenant B must not be able to read it.
    other = await client.get(f"/v1/suppliers/{supplier_id}", headers=_bearer(token_b))
    assert other.status_code == 404


async def test_cross_tenant_patch_returns_404(client: AsyncClient) -> None:
    token_a, token_b = await _register_two_tenants(client)
    supplier_id = await _create_supplier_for(client, token_a)

    response = await client.patch(
        f"/v1/suppliers/{supplier_id}",
        headers=_bearer(token_b),
        json={"legal_name": "Tenant B Hijack LLC"},
    )
    assert response.status_code == 404

    # Verify the supplier is unchanged from Tenant A's perspective.
    own = await client.get(f"/v1/suppliers/{supplier_id}", headers=_bearer(token_a))
    assert own.status_code == 200, own.text
    assert own.json()["legal_name"] == _SUPPLIER_PAYLOAD["legal_name"]


async def test_cross_tenant_delete_returns_404(client: AsyncClient) -> None:
    token_a, token_b = await _register_two_tenants(client)
    supplier_id = await _create_supplier_for(client, token_a)

    response = await client.delete(
        f"/v1/suppliers/{supplier_id}", headers=_bearer(token_b)
    )
    assert response.status_code == 404

    # Tenant A still sees the supplier.
    own = await client.get(f"/v1/suppliers/{supplier_id}", headers=_bearer(token_a))
    assert own.status_code == 200, own.text


async def test_list_does_not_leak_other_tenants(client: AsyncClient) -> None:
    token_a, token_b = await _register_two_tenants(client)
    a_supplier = await _create_supplier_for(client, token_a, legal_name="A Co LLC")
    b_supplier = await _create_supplier_for(client, token_b, legal_name="B Co LLC")

    a_list = await client.get("/v1/suppliers", headers=_bearer(token_a))
    b_list = await client.get("/v1/suppliers", headers=_bearer(token_b))
    assert a_list.status_code == 200, a_list.text
    assert b_list.status_code == 200, b_list.text

    a_ids = {row["id"] for row in a_list.json()}
    b_ids = {row["id"] for row in b_list.json()}
    assert a_supplier in a_ids and b_supplier not in a_ids
    assert b_supplier in b_ids and a_supplier not in b_ids
