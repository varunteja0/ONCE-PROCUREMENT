"""End-to-end tests for the /v1/risk-schedules API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.utils.canonical_json import payload_sha256
from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_BASE_SUPPLIER: dict[str, Any] = {"legal_name": "Coastline Trucking Co"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    res = await client.post("/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(token))
    assert res.status_code == 201
    return res.json()["id"]


def _payload(supplier_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "line_of_business": "commercial_auto",
        "schedule_type": "vehicle_schedule",
        "effective_date": "2024-06-01",
        "expiration_date": "2025-06-01",
        "total_value_cents": 350_000_00,
        "items": [
            {
                "vin": "1FUJGEDV5CLBP1234",
                "year": 2019,
                "make": "Freightliner",
                "model": "Cascadia",
                "value_cents": 175_000_00,
            },
            {
                "vin": "1FUJGEDV5CLBP5678",
                "year": 2021,
                "make": "Kenworth",
                "model": "T680",
                "value_cents": 175_000_00,
            },
        ],
    }
    base.update(overrides)
    return base


async def test_create_happy_and_hash_and_count_auto(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    body_in = _payload(sup)

    res = await client.post("/v1/risk-schedules", json=body_in)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["item_count"] == 2
    assert body["items_hash"] == payload_sha256(body_in["items"])
    assert body["schedule_type"] == "vehicle_schedule"


async def test_create_rejects_period_inverted(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/risk-schedules",
        json=_payload(sup, effective_date="2025-06-01", expiration_date="2024-06-01"),
    )
    assert res.status_code == 422


async def test_create_allows_empty_items_with_zero_count(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/risk-schedules", json=_payload(sup, items=[], total_value_cents=None)
    )
    assert res.status_code == 201
    body = res.json()
    assert body["item_count"] == 0
    assert body["items"] == []
    assert body["items_hash"] == payload_sha256([])


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
        "/v1/risk-schedules",
        json=_payload(sup_a),
        headers=_bearer(b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_list_filters_and_paginates(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    for i in range(3):
        r = await client.post(
            "/v1/risk-schedules",
            json=_payload(sup, schedule_type=f"vehicle_schedule_{i}"),
        )
        assert r.status_code == 201

    res = await client.get(f"/v1/risk-schedules?supplier_id={sup}&limit=2")
    body = res.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_update_items_recomputes_hash_and_count(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    created = await client.post("/v1/risk-schedules", json=_payload(sup))
    assert created.status_code == 201
    rs_id = created.json()["id"]
    original_hash = created.json()["items_hash"]

    new_items = [{"vin": "JUSTONE", "year": 2022, "value_cents": 100_00}]
    patched = await client.patch(
        f"/v1/risk-schedules/{rs_id}",
        json={"items": new_items},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["item_count"] == 1
    assert body["items_hash"] == payload_sha256(new_items)
    assert body["items_hash"] != original_hash


async def test_update_cross_tenant_404(client: AsyncClient) -> None:
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
    rs_id = (
        await client.post(
            "/v1/risk-schedules",
            json=_payload(sup_a),
            headers=_bearer(a.tokens.access_token),
        )
    ).json()["id"]

    res = await client.patch(
        f"/v1/risk-schedules/{rs_id}",
        json={"total_value_cents": 1},
        headers=_bearer(b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_delete_then_get_404(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    rs_id = (await client.post("/v1/risk-schedules", json=_payload(sup))).json()["id"]

    deleted = await client.delete(f"/v1/risk-schedules/{rs_id}")
    assert deleted.status_code == 204
    after = await client.get(f"/v1/risk-schedules/{rs_id}")
    assert after.status_code == 404
