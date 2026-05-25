"""Tests for refresh-token rotation (jti revocation)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.auth import TokenPair

pytestmark = pytest.mark.asyncio


_REGISTER_PAYLOAD = {
    "email": "rotate@example.com",
    "password": "Sup3rSecret!Pass",
    "full_name": "Rotate User",
    "tenant_name": "Rotate Co",
}


async def test_refresh_token_cannot_be_replayed(client: AsyncClient) -> None:
    """RFC 6749 §10.4 rotation — same refresh token must not work twice."""

    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text
    initial = TokenPair(**register.json())

    first = await client.post("/v1/auth/refresh", json={"refresh_token": initial.refresh_token})
    assert first.status_code == 200, first.text
    rotated = TokenPair(**first.json())
    assert rotated.refresh_token != initial.refresh_token

    # Replaying the original refresh token must now be rejected because
    # its ``jti`` is on the denylist.
    replay = await client.post("/v1/auth/refresh", json={"refresh_token": initial.refresh_token})
    assert replay.status_code == 401, replay.text
    body = replay.json()["detail"]
    assert body["code"] == "invalid_refresh_token"

    # The freshly-issued refresh token still works exactly once.
    second = await client.post("/v1/auth/refresh", json={"refresh_token": rotated.refresh_token})
    assert second.status_code == 200, second.text


async def test_refresh_token_without_jti_is_rejected(client: AsyncClient) -> None:
    """A hand-crafted refresh token missing ``jti`` must not be accepted."""

    from app.utils.security import create_refresh_token

    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text

    # Forge a refresh token without the jti claim using the same secret.
    me = await client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {register.json()['access_token']}"},
    )
    assert me.status_code == 200
    me_body = me.json()
    legacy_token = create_refresh_token(
        sub=me_body["id"],
        tenant_id=me_body["tenant_id"],
        extra_claims={"role": "owner"},
    )

    response = await client.post("/v1/auth/refresh", json={"refresh_token": legacy_token})
    assert response.status_code == 401, response.text
