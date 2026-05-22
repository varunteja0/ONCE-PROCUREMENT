"""End-to-end tests for the /v1/acord-forms API."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.utils.canonical_json import payload_sha256
from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


_BASE_SUPPLIER: dict[str, Any] = {"legal_name": "Northwind MGA LLC"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_supplier(client: AsyncClient, token: str) -> str:
    res = await client.post("/v1/suppliers", json=_BASE_SUPPLIER, headers=_bearer(token))
    assert res.status_code == 201
    return res.json()["id"]


def _payload(supplier_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "form_type": "acord_125",
        "form_version": "2016/03",
        "payload": {
            "applicant_name": "Sunrise Logistics",
            "fein": "12-3456789",
            "naics": "484121",
            "effective_date": "2025-01-01",
        },
        "effective_date": "2025-01-01",
        "expiration_date": "2026-01-01",
    }
    base.update(overrides)
    return base


async def test_create_happy_and_payload_hash_auto_computed(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    body_in = _payload(sup)

    res = await client.post("/v1/acord-forms", json=body_in)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["form_type"] == "acord_125"
    assert body["status"] == "draft"
    expected_hash = payload_sha256(body_in["payload"])
    assert body["payload_hash"] == expected_hash


async def test_create_rejects_invalid_form_type(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post("/v1/acord-forms", json=_payload(sup, form_type="acord_999"))
    assert res.status_code == 422


async def test_create_rejects_period_inverted(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    res = await client.post(
        "/v1/acord-forms",
        json=_payload(sup, effective_date="2026-01-01", expiration_date="2025-01-01"),
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
        "/v1/acord-forms",
        json=_payload(sup_a),
        headers=_bearer(b.tokens.access_token),
    )
    assert res.status_code == 404


async def test_list_paginates(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    for i in range(5):
        r = await client.post(
            "/v1/acord-forms",
            json=_payload(sup, payload={"i": i, "fein": "12-3456789"}),
        )
        assert r.status_code == 201

    res = await client.get(f"/v1/acord-forms?supplier_id={sup}&limit=2&offset=1")
    body = res.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


async def test_update_payload_recomputes_hash_and_supersedes_predecessor(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)

    original = await client.post("/v1/acord-forms", json=_payload(sup))
    assert original.status_code == 201
    original_id = original.json()["id"]
    original_hash = original.json()["payload_hash"]

    # Create a new revision form
    new_form = await client.post(
        "/v1/acord-forms",
        json=_payload(sup, payload={"applicant_name": "Sunrise Logistics v2"}),
    )
    new_id = new_form.json()["id"]

    # Update the new form to reference superseded_by (which on this entity means
    # the predecessor of *this* is something else; we model it by patching the
    # predecessor's superseded_by_id to point at the new form).
    patched = await client.patch(
        f"/v1/acord-forms/{original_id}",
        json={"superseded_by_id": new_id, "payload": {"applicant_name": "rev"}},
    )
    assert patched.status_code == 200
    body = patched.json()
    # status auto-flips to 'superseded' because we set superseded_by_id
    assert body["status"] == "superseded"
    assert body["superseded_by_id"] == new_id
    # hash recomputed from new payload
    assert body["payload_hash"] == payload_sha256({"applicant_name": "rev"})
    assert body["payload_hash"] != original_hash


async def test_update_self_supersede_is_422(
    auth_client: tuple[AsyncClient, Any],
) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    created_id = (await client.post("/v1/acord-forms", json=_payload(sup))).json()["id"]

    res = await client.patch(
        f"/v1/acord-forms/{created_id}",
        json={"superseded_by_id": created_id},
    )
    assert res.status_code == 422


async def test_delete_then_get_404(auth_client: tuple[AsyncClient, Any]) -> None:
    client, _ = auth_client
    token = client.headers["Authorization"].split(" ", 1)[1]
    sup = await _create_supplier(client, token)
    form_id = (await client.post("/v1/acord-forms", json=_payload(sup))).json()["id"]

    deleted = await client.delete(f"/v1/acord-forms/{form_id}")
    assert deleted.status_code == 204
    after = await client.get(f"/v1/acord-forms/{form_id}")
    assert after.status_code == 404
