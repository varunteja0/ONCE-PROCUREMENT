"""Tests for :class:`app.middleware.tenant_scope.TenantScopeMiddleware`.

The middleware extracts ``tenant_id`` and ``user_id`` from a Bearer JWT and
attaches them to ``request.state``. It is intentionally permissive — missing or
malformed tokens leave the state attributes ``None`` so downstream dependencies
can return the appropriate 401.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.tenant_scope import TenantScopeMiddleware
from app.utils.security import create_access_token, create_refresh_token

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TenantScopeMiddleware)

    @app.get("/state")
    async def state(request: Request) -> dict[str, str | None]:
        return {
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
        }

    @app.get("/health")
    async def health(request: Request) -> dict[str, str | None]:
        return {
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
        }

    @app.get("/v1/auth/login")
    async def login(request: Request) -> dict[str, str | None]:
        return {
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
        }

    @app.get("/verify/abc")
    async def verify(request: Request) -> dict[str, str | None]:
        return {
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
        }

    return app


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=_build_app()), base_url="http://t")


class TestStateExtraction:
    async def test_valid_access_token_sets_state(self) -> None:
        token = create_access_token(sub="user-1", tenant_id="tenant-1")
        async with await _new_client() as c:
            r = await c.get("/state", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["tenant_id"] == "tenant-1"
        assert body["user_id"] == "user-1"

    async def test_no_auth_header_leaves_state_none(self) -> None:
        async with await _new_client() as c:
            r = await c.get("/state")
        assert r.json() == {"tenant_id": None, "user_id": None}

    async def test_garbage_token_swallowed_state_none(self) -> None:
        async with await _new_client() as c:
            r = await c.get(
                "/state", headers={"Authorization": "Bearer not.a.real.jwt"}
            )
        assert r.status_code == 200
        assert r.json() == {"tenant_id": None, "user_id": None}

    async def test_non_bearer_scheme_ignored(self) -> None:
        async with await _new_client() as c:
            r = await c.get(
                "/state", headers={"Authorization": "Basic dXNlcjpwYXNz"}
            )
        assert r.json() == {"tenant_id": None, "user_id": None}

    async def test_refresh_token_rejected_as_access(self) -> None:
        # decode_token(expected_type="access") will raise for a refresh token,
        # which the middleware swallows.
        refresh = create_refresh_token(sub="u", tenant_id="t")
        async with await _new_client() as c:
            r = await c.get(
                "/state", headers={"Authorization": f"Bearer {refresh}"}
            )
        assert r.json() == {"tenant_id": None, "user_id": None}

    async def test_token_missing_tenant_id_leaves_tenant_none(self) -> None:
        token = create_access_token(sub="user-2", tenant_id=None)
        async with await _new_client() as c:
            r = await c.get(
                "/state", headers={"Authorization": f"Bearer {token}"}
            )
        body = r.json()
        assert body["user_id"] == "user-2"
        assert body["tenant_id"] is None

    async def test_bearer_lowercase_scheme_accepted(self) -> None:
        token = create_access_token(sub="u", tenant_id="t")
        async with await _new_client() as c:
            r = await c.get(
                "/state", headers={"Authorization": f"bearer {token}"}
            )
        assert r.json()["tenant_id"] == "t"


class TestSkipPrefixes:
    @pytest.mark.parametrize("path", ["/health", "/v1/auth/login", "/verify/abc"])
    async def test_skip_prefix_does_not_decode_jwt(self, path: str) -> None:
        async with await _new_client() as c:
            r = await c.get(
                path, headers={"Authorization": "Bearer garbage-token"}
            )
        assert r.status_code == 200
        # Skipped path → state untouched (both None).
        assert r.json() == {"tenant_id": None, "user_id": None}
