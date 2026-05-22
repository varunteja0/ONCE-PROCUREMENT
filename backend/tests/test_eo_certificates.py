"""End-to-end tests for the /v1/eo-certificates API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_BASE_SUPPLIER: dict[str, Any] = {"legal_name": "Sterling MGA LLC"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    res = await client.post("/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(token))
    assert res.status_code == 201
    return res.json()["id"]


def _payload(supplier_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "carrier_name": "Hanover Insurance",
        "policy_number": "EO-2024-7777",
        "coverage_amount_cents": 1_000_000_00,
        "aggregate_amount_cents": 2_000_000_00,
        "deductible_cents": 10_000_00,
        "effective_date": "2024-06-01",
        "expiration_date": "2025-06-01",
        "named_insured": "Sterling MGA LLC",
        "additional_insureds": ["Acme Carrier", "Beta Carrier"],
    }
    base.update(overrides)
    return base


async def test_create_happy(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post("/v1/eo-certificates", json=_payload(sup))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["coverage_amount_cents"] == 1_000_000_00
    assert body["status"] == "active"
    assert body["additional_insureds"] == ["Acme Carrier", "Beta Carrier"]


async def test_create_rejects_aggregate_below_per_claim(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/eo-certificates",
        json=_payload(sup, coverage_amount_cents=5_000_00, aggregate_amount_cents=1_000_00),
    )
    assert res.status_code == 422


async def test_create_rejects_period_inverted(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/eo-certificates",
        json=_payload(sup, effective_date="2025-06-01", expiration_date="2024-06-01"),
    )
    assert res.status_code == 422


async def test_create_negative_coverage_rejected(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/eo-certificates", json=_payload(sup, coverage_amount_cents=-1)
    )
    assert res.status_code == 422


async def test_cross_tenant_supplier_404(client: AsyncClient) -> None:
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
        "/v1/eo-certificates",
        json=_payload(sup_a),
        headers=_bearer(b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_list_and_paginate(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    for i in range(4):
        r = await client.post(
            "/v1/eo-certificates",
            json=_payload(sup, policy_number=f"EO-{i}"),
        )
        assert r.status_code == 201

    res = await client.get(f"/v1/eo-certificates?supplier_id={sup}&limit=3&offset=0")
    body = res.json()
    assert body["total"] == 4
    assert len(body["items"]) == 3
    assert body["limit"] == 3


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
    cert_id = (
        await client.post(
            "/v1/eo-certificates",
            json=_payload(sup_a),
            headers=_bearer(a.tokens.access_token),
        )
    ).json()["id"]

    patched = await client.patch(
        f"/v1/eo-certificates/{cert_id}",
        json={"status": "pending_renewal", "deductible_cents": 25_000_00},
        headers=_bearer(a.tokens.access_token),
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "pending_renewal"
    assert patched.json()["deductible_cents"] == 25_000_00

    cross = await client.patch(
        f"/v1/eo-certificates/{cert_id}",
        json={"status": "cancelled"},
        headers=_bearer(b.tokens.access_token),
    )
    assert cross.status_code == 404


async def test_delete_then_get_404(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    cert_id = (await client.post("/v1/eo-certificates", json=_payload(sup))).json()["id"]

    deleted = await client.delete(f"/v1/eo-certificates/{cert_id}")
    assert deleted.status_code == 204
    after = await client.get(f"/v1/eo-certificates/{cert_id}")
    assert after.status_code == 404
