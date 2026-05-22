"""Tests for shared pagination semantics across list endpoints.

The backend exposes three list endpoints with the same shape:
``GET /v1/suppliers``, ``/v1/submissions``, ``/v1/portals``. Each accepts
``limit``/``offset`` query parameters and surfaces an ``X-Total-Count`` header.
These tests pin the invariants those routes rely on.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import RegisteredUser

pytestmark = pytest.mark.asyncio


def _supplier_payload(legal_name: str) -> dict[str, object]:
    return {
        "legal_name": legal_name,
        "ein": "12-3456789",
        "naics_code": "524210",
    }


async def _seed_suppliers(
    client: AsyncClient, count: int
) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        r = await client.post(
            "/v1/suppliers", json=_supplier_payload(f"Supplier {i:03d}")
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


class TestSuppliersPagination:
    async def test_default_returns_all_when_under_default_limit(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await _seed_suppliers(client, 3)
        r = await client.get("/v1/suppliers")
        assert r.status_code == 200
        assert len(r.json()) == 3
        assert r.headers.get("X-Total-Count") == "3"

    async def test_limit_param_caps_results(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await _seed_suppliers(client, 5)
        r = await client.get("/v1/suppliers", params={"limit": 2})
        assert r.status_code == 200
        assert len(r.json()) == 2
        # Total count should still reflect the full set.
        assert r.headers.get("X-Total-Count") == "5"

    async def test_offset_skips_first_records(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await _seed_suppliers(client, 5)
        first = await client.get("/v1/suppliers", params={"limit": 2, "offset": 0})
        second = await client.get(
            "/v1/suppliers", params={"limit": 2, "offset": 2}
        )
        assert first.status_code == 200 and second.status_code == 200
        first_ids = {row["id"] for row in first.json()}
        second_ids = {row["id"] for row in second.json()}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.parametrize("bad_limit", [-1, 0, 201, 100000])
    async def test_limit_outside_range_returns_422(
        self,
        auth_client: tuple[AsyncClient, RegisteredUser],
        bad_limit: int,
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/suppliers", params={"limit": bad_limit})
        assert r.status_code == 422

    async def test_negative_offset_returns_422(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/suppliers", params={"offset": -1})
        assert r.status_code == 422

    async def test_total_count_header_is_zero_for_empty_tenant(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/suppliers")
        assert r.status_code == 200
        assert r.json() == []
        assert r.headers.get("X-Total-Count") == "0"


class TestPortalsPagination:
    async def test_lists_all_seeded_portals(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/portals")
        assert r.status_code == 200
        body = r.json()
        # Default conftest seeds 5 portals.
        assert body["total"] >= 5
        assert len(body["items"]) == body["total"]

    async def test_limit_caps_items_but_not_total(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/portals", params={"limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 2
        assert body["total"] >= 5

    async def test_is_supported_filter_works(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get(
            "/v1/portals", params={"is_supported": "true"}
        )
        assert r.status_code == 200
        assert all(p["is_supported"] for p in r.json()["items"])
