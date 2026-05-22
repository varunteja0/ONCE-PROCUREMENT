"""Error envelope shape tests.

Verifies that the FastAPI error responses across the API conform to a
predictable envelope:

* ``HTTPException(detail={"code": ..., "message": ...})`` → JSON
  ``{"detail": {"code": ..., "message": ...}}`` with the documented status.
* validation errors → 422 with ``detail`` being a list of error records.
* unknown routes → 404 with a ``detail`` key.

These tests live separately from per-route tests so the envelope contract is
exercised in isolation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_unknown_route_returns_404_with_detail(client: AsyncClient) -> None:
    r = await client.get("/v1/this-route-does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body


async def test_invalid_register_payload_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/v1/auth/register",
        json={"email": "not-an-email", "password": "x"},
    )
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body.get("detail"), list)
    # Each pydantic v2 error record has a `loc` tuple.
    assert all("loc" in err for err in body["detail"])


async def test_invalid_login_payload_returns_422(client: AsyncClient) -> None:
    r = await client.post("/v1/auth/login", json={})
    assert r.status_code == 422


async def test_login_with_bad_credentials_returns_structured_detail(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "no-such-account-1!"},
    )
    assert r.status_code == 401
    body = r.json()
    detail = body["detail"]
    # Structured envelope: `code` + `message`.
    assert isinstance(detail, dict)
    assert detail.get("code") == "invalid_credentials"
    assert isinstance(detail.get("message"), str)
    # WWW-Authenticate header surfaced by FastAPI on 401 (Bearer scheme).
    assert "www-authenticate" in {k.lower() for k in r.headers.keys()}


async def test_unauthed_protected_route_returns_401(client: AsyncClient) -> None:
    r = await client.get("/v1/suppliers")
    assert r.status_code == 401
    assert "detail" in r.json()


async def test_password_too_short_returns_422_with_string_too_short_error(
    client: AsyncClient,
) -> None:
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": "tiny@example.com",
            "password": "tiny",  # < 8 chars
            "full_name": "Tiny",
            "tenant_name": "Tiny Co",
        },
    )
    assert r.status_code == 422
    errors = r.json()["detail"]
    assert any("password" in err["loc"] for err in errors)
