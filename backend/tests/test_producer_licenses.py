"""End-to-end tests for the /v1/producer-licenses API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_BASE_SUPPLIER: dict[str, Any] = {"legal_name": "Apex Brokers Inc"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    res = await client.post("/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(token))
    assert res.status_code == 201
    return res.json()["id"]


def _payload(supplier_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "state": "TX",
        "license_number": "TX-PRO-12345",
        "license_type": "resident_producer",
        "licensee_name": "Apex Brokers Inc",
        "npn": "8675309",
        "effective_date": "2024-01-01",
        "expiration_date": "2026-01-01",
        "lines_authorized": ["commercial_auto", "general_liability"],
    }
    base.update(overrides)
    return base


async def test_create_producer_license_happy(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post("/v1/producer-licenses", json=_payload(sup))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["state"] == "TX"
    assert body["license_number"] == "TX-PRO-12345"
    assert body["status"] == "active"
    assert body["lines_authorized"] == ["commercial_auto", "general_liability"]


async def test_create_rejects_invalid_state(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/producer-licenses", json=_payload(sup, state="ZZ")
    )
    assert res.status_code == 422


async def test_create_rejects_expiration_before_effective(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/producer-licenses",
        json=_payload(sup, effective_date="2026-01-01", expiration_date="2025-01-01"),
    )
    assert res.status_code == 422


async def test_create_cross_tenant_supplier_404(client: AsyncClient) -> None:
    a = await register_user(
        client, email="a@e.com", password="StrongPass-A1!", tenant_name="A"
    )
    b = await register_user(
        client, email="b@e.com", password="StrongPass-B2!", tenant_name="B"
    )
    sup_a = (
        await client.post(
            "/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(a.tokens.access_token)
        )
    ).json()["id"]
    res = await client.post(
        "/v1/producer-licenses",
        json=_payload(sup_a),
        headers=_bearer(b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_duplicate_license_returns_409(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    first = await client.post("/v1/producer-licenses", json=_payload(sup))
    assert first.status_code == 201
    dup = await client.post("/v1/producer-licenses", json=_payload(sup))
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "license_already_exists"


async def test_list_filters_by_supplier_and_paginates(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    for state, num in (("TX", "1"), ("CA", "2"), ("NY", "3")):
        r = await client.post(
            "/v1/producer-licenses",
            json=_payload(sup, state=state, license_number=f"{state}-{num}"),
        )
        assert r.status_code == 201

    res = await client.get(f"/v1/producer-licenses?supplier_id={sup}&limit=2")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_partial_and_cross_tenant(client: AsyncClient) -> None:
    a = await register_user(
        client, email="a@e.com", password="StrongPass-A1!", tenant_name="A"
    )
    b = await register_user(
        client, email="b@e.com", password="StrongPass-B2!", tenant_name="B"
    )
    sup_a = (
        await client.post(
            "/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(a.tokens.access_token)
        )
    ).json()["id"]
    lic_id = (
        await client.post(
            "/v1/producer-licenses",
            json=_payload(sup_a),
            headers=_bearer(a.tokens.access_token),
        )
    ).json()["id"]

    patched = await client.patch(
        f"/v1/producer-licenses/{lic_id}",
        json={"status": "pending_renewal"},
        headers=_bearer(a.tokens.access_token),
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "pending_renewal"

    cross = await client.patch(
        f"/v1/producer-licenses/{lic_id}",
        json={"status": "revoked"},
        headers=_bearer(b.tokens.access_token),
    )
    assert cross.status_code == 404


async def test_delete_works_then_get_404(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    lic_id = (
        await client.post("/v1/producer-licenses", json=_payload(sup))
    ).json()["id"]

    deleted = await client.delete(f"/v1/producer-licenses/{lic_id}")
    assert deleted.status_code == 204
    res = await client.get(f"/v1/producer-licenses/{lic_id}")
    assert res.status_code == 404
