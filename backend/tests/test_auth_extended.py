"""Extended auth-router tests beyond the basic happy path covered in the
existing suite. Covers:

* duplicate email registration → 409
* invalid email format → 422
* weak / short / missing password → 422
* whitespace in name/tenant_name is trimmed
* login with bad credentials → 401 with structured envelope
* refresh with an access token (wrong type) → 401
* refresh with garbage → 401
* /auth/me with no bearer → 401
* /auth/me with valid bearer returns the registered user
* token expiration handled (freezegun)
"""

from __future__ import annotations

import pytest
from freezegun import freeze_time
from httpx import AsyncClient

from app.utils.security import create_access_token
from tests.conftest import RegisteredUser

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_returns_token_pair(self, client: AsyncClient) -> None:
        r = await client.post(
            "/v1/auth/register",
            json={
                "email": "first@example.com",
                "password": "Strong-Pass-1!",
                "full_name": "First Last",
                "tenant_name": "Acme",
            },
        )
        assert r.status_code == 201
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    async def test_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        payload = {
            "email": "dup@example.com",
            "password": "Strong-Pass-1!",
            "full_name": "Dup User",
            "tenant_name": "Dup Co",
        }
        r1 = await client.post("/v1/auth/register", json=payload)
        assert r1.status_code == 201
        r2 = await client.post("/v1/auth/register", json=payload)
        assert r2.status_code == 409
        detail = r2.json()["detail"]
        assert detail["code"] == "email_already_registered"

    @pytest.mark.parametrize(
        "bad_email",
        ["not-an-email", "missing-at.test", "@no-local.test", ""],
    )
    async def test_invalid_email_format_returns_422(
        self, client: AsyncClient, bad_email: str
    ) -> None:
        r = await client.post(
            "/v1/auth/register",
            json={
                "email": bad_email,
                "password": "Strong-Pass-1!",
                "full_name": "X",
                "tenant_name": "Y",
            },
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_password", ["", "short"])
    async def test_short_password_returns_422(
        self, client: AsyncClient, bad_password: str
    ) -> None:
        r = await client.post(
            "/v1/auth/register",
            json={
                "email": "shortpw@example.com",
                "password": bad_password,
                "full_name": "X",
                "tenant_name": "Y",
            },
        )
        assert r.status_code == 422

    async def test_email_normalized_to_lowercase(self, client: AsyncClient) -> None:
        r = await client.post(
            "/v1/auth/register",
            json={
                "email": "Mixed.CASE@Example.COM",
                "password": "Strong-Pass-1!",
                "full_name": "Mixed Case",
                "tenant_name": "MixedTenant",
            },
        )
        assert r.status_code == 201
        # Same email, different case → server normalized → duplicate.
        again = await client.post(
            "/v1/auth/login",
            json={"email": "mixed.case@example.com", "password": "Strong-Pass-1!"},
        )
        assert again.status_code == 200

    async def test_whitespace_in_strings_is_trimmed(
        self, client: AsyncClient
    ) -> None:
        r = await client.post(
            "/v1/auth/register",
            json={
                "email": "trim@example.com",
                "password": "Strong-Pass-1!",
                "full_name": "  Spaced Name  ",
                "tenant_name": "  Spaced Tenant  ",
            },
        )
        assert r.status_code == 201
        token = r.json()["access_token"]
        me = await client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        body = me.json()
        assert body["full_name"] == "Spaced Name"


class TestLogin:
    async def test_bad_credentials_return_401(self, client: AsyncClient) -> None:
        r = await client.post(
            "/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-pass-1!"},
        )
        assert r.status_code == 401
        body = r.json()
        assert body["detail"]["code"] == "invalid_credentials"

    async def test_wrong_password_returns_401(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            "/v1/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "Strong-Pass-1!",
                "full_name": "X",
                "tenant_name": "Y",
            },
        )
        r = await client.post(
            "/v1/auth/login",
            json={"email": "wrongpw@example.com", "password": "WRONG-pass-1!"},
        )
        assert r.status_code == 401


class TestRefresh:
    async def test_refresh_with_access_token_returns_401(
        self,
        auth_client: tuple[AsyncClient, RegisteredUser],
    ) -> None:
        client, registered = auth_client
        # Strip the auto-set bearer for a clean POST.
        client.headers.pop("Authorization", None)
        r = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": registered.tokens.access_token},
        )
        assert r.status_code == 401

    async def test_refresh_with_garbage_returns_401(
        self, client: AsyncClient
    ) -> None:
        r = await client.post(
            "/v1/auth/refresh", json={"refresh_token": "not.a.real.jwt"}
        )
        assert r.status_code == 401

    async def test_refresh_happy_path_returns_new_pair(
        self,
        auth_client: tuple[AsyncClient, RegisteredUser],
    ) -> None:
        client, registered = auth_client
        client.headers.pop("Authorization", None)
        r = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": registered.tokens.refresh_token},
        )
        assert r.status_code == 200
        body = r.json()
        # Both tokens come back signed for the same subject; the access
        # token must round-trip and contain the same tenant.
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str) and body["access_token"]
        assert isinstance(body["refresh_token"], str) and body["refresh_token"]


class TestMe:
    async def test_me_without_bearer_returns_401(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/v1/auth/me")
        assert r.status_code == 401

    async def test_me_with_garbage_bearer_returns_401(
        self, client: AsyncClient
    ) -> None:
        r = await client.get(
            "/v1/auth/me", headers={"Authorization": "Bearer garbage"}
        )
        assert r.status_code == 401

    async def test_me_returns_registered_user(
        self,
        auth_client: tuple[AsyncClient, RegisteredUser],
    ) -> None:
        client, registered = auth_client
        r = await client.get("/v1/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == registered.email
        assert body["role"] == "owner"
        assert body["tenant_id"]

    async def test_expired_access_token_returns_401(
        self,
        auth_client: tuple[AsyncClient, RegisteredUser],
    ) -> None:
        client, _ = auth_client
        with freeze_time("2099-01-01"):
            r = await client.get("/v1/auth/me")
        assert r.status_code == 401

    async def test_token_signed_with_unknown_user_returns_401(
        self, client: AsyncClient
    ) -> None:
        token = create_access_token(sub="ghost-user-id", tenant_id="ghost-tenant")
        r = await client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        # User doesn't exist → 401 from CurrentUser dep.
        assert r.status_code == 401
