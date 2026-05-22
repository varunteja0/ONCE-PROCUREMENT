"""Tests for the /v1/portals endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models import PortalPlatform
from tests.conftest import RegisteredUser
from tests.factories import make_portal

pytestmark = pytest.mark.asyncio


class TestList:
    async def test_unauth_returns_401(self, client: AsyncClient) -> None:
        r = await client.get("/v1/portals")
        assert r.status_code == 401

    async def test_returns_seeded_portals(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/portals")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 5
        assert all("platform" in p for p in body["items"])

    async def test_total_header_matches_envelope(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/portals")
        assert r.headers.get("X-Total-Count") == str(r.json()["total"])

    async def test_is_supported_true_filter(
        self, auth_client, async_session
    ) -> None:
        # Seeded portals are all is_supported=True. Add one unsupported.
        await make_portal(
            async_session,
            platform=PortalPlatform.GUIDEWIRE,
            is_supported=False,
        )
        await async_session.commit()
        client, _ = auth_client
        r = await client.get("/v1/portals", params={"is_supported": "true"})
        assert all(p["is_supported"] for p in r.json()["items"])

    async def test_is_supported_false_filter(
        self, auth_client, async_session
    ) -> None:
        await make_portal(
            async_session,
            platform=PortalPlatform.HAWKSOFT,
            is_supported=False,
        )
        await async_session.commit()
        client, _ = auth_client
        r = await client.get("/v1/portals", params={"is_supported": "false"})
        items = r.json()["items"]
        assert items, "expected at least one unsupported portal"
        assert all(p["is_supported"] is False for p in items)


class TestGetById:
    async def test_unknown_returns_404(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        r = await client.get("/v1/portals/no-such-id")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "portal_not_found"

    async def test_existing_returns_200(
        self, auth_client: tuple[AsyncClient, RegisteredUser]
    ) -> None:
        client, _ = auth_client
        listed = await client.get("/v1/portals")
        portal_id = listed.json()["items"][0]["id"]
        r = await client.get(f"/v1/portals/{portal_id}")
        assert r.status_code == 200
        assert r.json()["id"] == portal_id
