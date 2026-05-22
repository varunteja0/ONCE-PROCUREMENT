"""End-to-end tests for the /v1/loss-runs API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_BASE_SUPPLIER: dict[str, Any] = {
    "legal_name": "Acme Trucking LLC",
    "primary_email": "ops@acme.example",
}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(token)
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _payload(supplier_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "carrier_name": "Progressive Commercial",
        "line_of_business": "commercial_auto",
        "total_premium_cents": 12_500_00,
        "total_incurred_cents": 8_400_00,
        "total_paid_cents": 7_900_00,
        "claim_count": 4,
    }
    base.update(overrides)
    return base


async def test_create_loss_run_happy_path(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    supplier_id = await _create_supplier(client, client.headers["Authorization"].split(" ", 1)[1])

    response = await client.post("/v1/loss-runs", json=_payload(supplier_id))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["supplier_id"] == supplier_id
    assert body["carrier_name"] == "Progressive Commercial"
    assert body["line_of_business"] == "commercial_auto"
    assert body["status"] == "uploaded"
    assert body["total_premium_cents"] == 12_500_00
    assert body["id"]
    assert body["tenant_id"]


async def test_create_loss_run_rejects_period_inverted(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    supplier_id = await _create_supplier(client, token)

    response = await client.post(
        "/v1/loss-runs",
        json=_payload(supplier_id, period_start="2024-12-31", period_end="2024-01-01"),
    )
    assert response.status_code == 422


async def test_create_loss_run_rejects_invalid_line_of_business(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    supplier_id = await _create_supplier(client, token)

    response = await client.post(
        "/v1/loss-runs",
        json=_payload(supplier_id, line_of_business="not_a_real_line"),
    )
    assert response.status_code == 422


async def test_create_loss_run_cross_tenant_supplier_returns_404(
    client: AsyncClient,
) -> None:
    tenant_a = await register_user(
        client, email="a@example.com", password="StrongPass-A1!", tenant_name="A"
    )
    tenant_b = await register_user(
        client, email="b@example.com", password="StrongPass-B2!", tenant_name="B"
    )

    supplier_a = (
        await client.post(
            "/v1/suppliers",
            json=_BASE_SUPPLIER,
            headers=_bearer(tenant_a.tokens.access_token),
        )
    ).json()["id"]

    response = await client.post(
        "/v1/loss-runs",
        json=_payload(supplier_a),
        headers=_bearer(tenant_b.tokens.access_token),
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "supplier_not_found"


async def test_list_loss_runs_filters_by_supplier_and_paginates(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup1 = await _create_supplier(client, token)
    # Create second supplier
    other = await client.post(
        "/v1/suppliers",
        json={"legal_name": "Other Co"},
        headers=_bearer(token),
    )
    sup2 = other.json()["id"]

    for i in range(3):
        r = await client.post(
            "/v1/loss-runs",
            json=_payload(sup1, carrier_name=f"Carrier {i}"),
        )
        assert r.status_code == 201
    r = await client.post("/v1/loss-runs", json=_payload(sup2))
    assert r.status_code == 201

    res = await client.get(f"/v1/loss-runs?supplier_id={sup1}&limit=2&offset=0")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2
    assert all(item["supplier_id"] == sup1 for item in body["items"])

    res2 = await client.get(f"/v1/loss-runs?supplier_id={sup1}&limit=2&offset=2")
    assert res2.status_code == 200
    assert len(res2.json()["items"]) == 1


async def test_get_loss_run_cross_tenant_returns_404(client: AsyncClient) -> None:
    tenant_a = await register_user(
        client, email="a2@example.com", password="StrongPass-A1!", tenant_name="A2"
    )
    tenant_b = await register_user(
        client, email="b2@example.com", password="StrongPass-B2!", tenant_name="B2"
    )

    sup_a = (
        await client.post(
            "/v1/suppliers",
            json=_BASE_SUPPLIER,
            headers=_bearer(tenant_a.tokens.access_token),
        )
    ).json()["id"]
    created = await client.post(
        "/v1/loss-runs",
        json=_payload(sup_a),
        headers=_bearer(tenant_a.tokens.access_token),
    )
    assert created.status_code == 201
    lr_id = created.json()["id"]

    res = await client.get(
        f"/v1/loss-runs/{lr_id}",
        headers=_bearer(tenant_b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_update_loss_run_partial_and_cross_tenant(
    client: AsyncClient,
) -> None:
    tenant_a = await register_user(
        client, email="a3@example.com", password="StrongPass-A1!", tenant_name="A3"
    )
    tenant_b = await register_user(
        client, email="b3@example.com", password="StrongPass-B2!", tenant_name="B3"
    )

    sup_a = (
        await client.post(
            "/v1/suppliers",
            json=_BASE_SUPPLIER,
            headers=_bearer(tenant_a.tokens.access_token),
        )
    ).json()["id"]
    lr_id = (
        await client.post(
            "/v1/loss-runs",
            json=_payload(sup_a),
            headers=_bearer(tenant_a.tokens.access_token),
        )
    ).json()["id"]

    patch = await client.patch(
        f"/v1/loss-runs/{lr_id}",
        json={"status": "parsed", "claim_count": 5},
        headers=_bearer(tenant_a.tokens.access_token),
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["status"] == "parsed"
    assert body["claim_count"] == 5
    assert body["carrier_name"] == "Progressive Commercial"  # unchanged

    # Cross-tenant patch must 404.
    bad = await client.patch(
        f"/v1/loss-runs/{lr_id}",
        json={"status": "error"},
        headers=_bearer(tenant_b.tokens.access_token),
    )
    assert bad.status_code == 404


async def test_delete_loss_run_then_get_returns_404(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    supplier_id = await _create_supplier(client, token)

    created = await client.post("/v1/loss-runs", json=_payload(supplier_id))
    assert created.status_code == 201
    lr_id = created.json()["id"]

    deleted = await client.delete(f"/v1/loss-runs/{lr_id}")
    assert deleted.status_code == 204

    after = await client.get(f"/v1/loss-runs/{lr_id}")
    assert after.status_code == 404

    again = await client.delete(f"/v1/loss-runs/{lr_id}")
    assert again.status_code == 404
