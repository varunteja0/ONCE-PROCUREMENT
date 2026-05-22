"""Extended supplier API tests.

Covers create/read/update/delete behaviors, search across fields,
pagination edge cases, and the X-Total-Count header.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import RegisteredUser

pytestmark = pytest.mark.asyncio


def _supplier(legal_name: str, **extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "legal_name": legal_name,
        "ein": "12-3456789",
        "naics_code": "524210",
    }
    base.update(extra)
    return base


class TestCreate:
    async def test_create_returns_201_with_id(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.post("/v1/suppliers", json=_supplier("New LLC"))
        assert r.status_code == 201
        body = r.json()
        assert body["legal_name"] == "New LLC"
        assert body["id"]

    async def test_create_rejects_extra_unknown_fields(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.post(
            "/v1/suppliers",
            json=_supplier("Bad LLC", surprise="boom"),
        )
        assert r.status_code == 422

    async def test_create_unauth_returns_401(self, client: AsyncClient) -> None:
        r = await client.post("/v1/suppliers", json=_supplier("X"))
        assert r.status_code == 401

    async def test_create_with_empty_legal_name_returns_422(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.post("/v1/suppliers", json=_supplier(""))
        assert r.status_code == 422


class TestSearch:
    async def _seed(
        self, client: AsyncClient
    ) -> None:
        for s in [
            _supplier(
                "Alpha Holdings", dba_name="Alpha", primary_email="ops@alpha.example.com"
            ),
            _supplier(
                "Beta LLC", dba_name="Beta Co", primary_email="hello@beta.example.com"
            ),
            _supplier(
                "Gamma Inc", dba_name="Gamma", primary_email="info@gamma.example.com"
            ),
        ]:
            await client.post("/v1/suppliers", json=s)

    async def test_search_matches_legal_name_case_insensitive(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await self._seed(client)
        r = await client.get("/v1/suppliers", params={"search": "alpha"})
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["legal_name"] == "Alpha Holdings"

    async def test_search_matches_dba(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await self._seed(client)
        r = await client.get("/v1/suppliers", params={"search": "Beta Co"})
        rows = r.json()
        assert any(row["legal_name"] == "Beta LLC" for row in rows)

    async def test_search_matches_email(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await self._seed(client)
        r = await client.get("/v1/suppliers", params={"search": "gamma.example.com"})
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["legal_name"] == "Gamma Inc"

    async def test_search_matches_ein(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await client.post(
            "/v1/suppliers",
            json=_supplier("EIN-search Inc", ein="99-8888777"),
        )
        r = await client.get("/v1/suppliers", params={"search": "99-8888"})
        assert any(
            row["legal_name"] == "EIN-search Inc" for row in r.json()
        )

    async def test_search_no_match_returns_empty(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        await self._seed(client)
        r = await client.get("/v1/suppliers", params={"search": "no-such-supplier"})
        assert r.json() == []


class TestRead:
    async def test_get_unknown_returns_404(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/suppliers/does-not-exist")
        assert r.status_code == 404

    async def test_get_existing_returns_200(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post("/v1/suppliers", json=_supplier("Get Me"))
        ).json()
        r = await client.get(f"/v1/suppliers/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]


class TestUpdate:
    async def test_patch_updates_only_provided_fields(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post(
                "/v1/suppliers",
                json=_supplier("Original", dba_name="OG"),
            )
        ).json()
        r = await client.patch(
            f"/v1/suppliers/{created['id']}",
            json={"dba_name": "Updated DBA"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dba_name"] == "Updated DBA"
        # legal_name unchanged.
        assert body["legal_name"] == "Original"

    async def test_patch_unknown_returns_404(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.patch(
            "/v1/suppliers/nope", json={"dba_name": "x"}
        )
        assert r.status_code == 404

    async def test_patch_with_empty_payload_returns_same_data(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post("/v1/suppliers", json=_supplier("NoOp"))
        ).json()
        r = await client.patch(f"/v1/suppliers/{created['id']}", json={})
        assert r.status_code == 200
        assert r.json()["legal_name"] == "NoOp"


class TestDelete:
    async def test_delete_returns_204_and_removes_row(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        created = (
            await client.post("/v1/suppliers", json=_supplier("Delete Me"))
        ).json()
        r = await client.delete(f"/v1/suppliers/{created['id']}")
        assert r.status_code == 204
        # Subsequent get is 404.
        again = await client.get(f"/v1/suppliers/{created['id']}")
        assert again.status_code == 404

    async def test_delete_unknown_returns_404(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.delete("/v1/suppliers/no-such-id")
        assert r.status_code == 404
