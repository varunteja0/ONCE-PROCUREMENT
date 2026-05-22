"""Tests for the public auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.auth import TokenPair

pytestmark = pytest.mark.asyncio


_REGISTER_PAYLOAD: dict[str, str] = {
    "email": "auth-user@example.com",
    "password": "SuperS3cret!",
    "full_name": "Auth Tester",
    "tenant_name": "Auth Tenant",
}


async def test_register_returns_201_and_token_pair(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)

    assert response.status_code == 201, response.text
    body = response.json()
    tokens = TokenPair(**body)
    assert tokens.token_type == "bearer"
    assert tokens.access_token and tokens.refresh_token
    assert tokens.access_token != tokens.refresh_token


async def test_login_with_correct_credentials_returns_tokens(client: AsyncClient) -> None:
    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text

    response = await client.post(
        "/v1/auth/login",
        json={
            "email": _REGISTER_PAYLOAD["email"],
            "password": _REGISTER_PAYLOAD["password"],
        },
    )

    assert response.status_code == 200, response.text
    tokens = TokenPair(**response.json())
    assert tokens.access_token
    assert tokens.refresh_token


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text

    response = await client.post(
        "/v1/auth/login",
        json={"email": _REGISTER_PAYLOAD["email"], "password": "Wr0ng-password!"},
    )

    assert response.status_code == 401
    body = response.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        assert detail.get("code") == "invalid_credentials"


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-no-account"},
    )

    assert response.status_code == 401


async def test_me_returns_authenticated_user_info(client: AsyncClient) -> None:
    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text
    tokens = TokenPair(**register.json())

    response = await client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == _REGISTER_PAYLOAD["email"]
    assert body["full_name"] == _REGISTER_PAYLOAD["full_name"]
    assert body["role"]
    assert body["tenant_id"]
    assert body["id"]


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/v1/auth/me")
    assert response.status_code == 401


async def test_refresh_issues_a_new_token_pair(client: AsyncClient) -> None:
    register = await client.post("/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert register.status_code == 201, register.text
    initial = TokenPair(**register.json())

    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": initial.refresh_token},
    )

    assert response.status_code == 200, response.text
    refreshed = TokenPair(**response.json())
    assert refreshed.access_token
    assert refreshed.refresh_token

    me = await client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.access_token}"},
    )
    assert me.status_code == 200, me.text


async def test_refresh_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "not-a-real-jwt"},
    )
    assert response.status_code == 401
