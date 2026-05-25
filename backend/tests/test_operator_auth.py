"""Tests for cockpit operator authentication.

Covers login (happy + denied), weak-password rejection at set time,
lockout, MFA stub, refresh rotation, revocation, and token isolation
from the tenant JWT secret.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.db as app_db
from app.api.cockpit.router import cockpit_router
from app.config import settings
from app.middleware.operator_act_as import OperatorActAsMiddleware
from app.models import Operator, OperatorRole, OperatorStatus
from app.services import operator_auth
from app.utils.account_lockout import reset_default_tracker

pytestmark = pytest.mark.asyncio


STRONG_PWD = "C0ckpit-S3cret-Founder!2026"
WEAK_PWD = "password"


def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a known cockpit secret and disable rate-limit shenanigans."""

    monkeypatch.setattr(settings, "cockpit_jwt_secret_key", "test-cockpit-secret-" + "y" * 32)
    monkeypatch.setenv("ACCOUNT_LOCKOUT_MAX_FAILS", "3")
    monkeypatch.setenv("ACCOUNT_LOCKOUT_WINDOW_SEC", "60")
    monkeypatch.setenv("ACCOUNT_LOCKOUT_DURATION_SEC", "60")
    reset_default_tracker()


@pytest_asyncio.fixture
async def cockpit_app(_test_engine, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    _isolated_env(monkeypatch)
    app = FastAPI(title="cockpit-test")
    app.add_middleware(OperatorActAsMiddleware)
    app.include_router(cockpit_router)
    return app


@pytest_asyncio.fixture
async def cockpit_client(cockpit_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=cockpit_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _seed_operator(
    *,
    email: str = "founder@once.dev",
    role: str = OperatorRole.FOUNDER.value,
    status: str = OperatorStatus.ACTIVE.value,
    mfa_required: bool = False,
    password: str = STRONG_PWD,
) -> Operator:
    async with app_db.AsyncSessionLocal() as session:
        op = Operator(
            email=email,
            hashed_password=operator_auth.operator_password_hash(password),
            role=role,
            status=status,
            mfa_required=mfa_required,
        )
        session.add(op)
        await session.commit()
        await session.refresh(op)
        return op


# ---------------------------------------------------------------------------
# 1. Login happy path returns a token pair
# ---------------------------------------------------------------------------


async def test_login_happy_path_returns_tokens(cockpit_client: AsyncClient) -> None:
    await _seed_operator()
    resp = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "founder@once.dev", "password": STRONG_PWD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] == 15 * 60
    # Cookies set
    set_cookie = resp.headers.get_list("set-cookie")
    joined = " ".join(set_cookie)
    assert "once_cockpit_access=" in joined
    assert "once_cockpit_refresh=" in joined


# ---------------------------------------------------------------------------
# 2. Weak password rejected at set time
# ---------------------------------------------------------------------------


async def test_weak_password_rejected_at_set_time() -> None:
    with pytest.raises(operator_auth.OperatorAuthError) as exc:
        operator_auth.evaluate_operator_password(WEAK_PWD)
    assert exc.value.code == "weak_password"
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# 3. Suspended operator cannot login
# ---------------------------------------------------------------------------


async def test_suspended_operator_cannot_login(cockpit_client: AsyncClient) -> None:
    await _seed_operator(email="alice@once.dev", status=OperatorStatus.SUSPENDED.value)
    resp = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "alice@once.dev", "password": STRONG_PWD},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "operator_suspended"


# ---------------------------------------------------------------------------
# 4. Lockout after N failures
# ---------------------------------------------------------------------------


async def test_lockout_after_repeated_failures(cockpit_client: AsyncClient) -> None:
    await _seed_operator(email="bob@once.dev")
    for _ in range(3):
        bad = await cockpit_client.post(
            "/cockpit/auth/login",
            json={"email": "bob@once.dev", "password": "wrong-password-aaa"},
        )
        assert bad.status_code == 401
    locked = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "bob@once.dev", "password": STRONG_PWD},
    )
    assert locked.status_code == 429
    assert locked.json()["detail"]["code"] == "account_locked"


# ---------------------------------------------------------------------------
# 5. MFA-required operator without TOTP -> 403 mfa_required
# ---------------------------------------------------------------------------


async def test_mfa_required_without_totp(cockpit_client: AsyncClient) -> None:
    await _seed_operator(email="mfa@once.dev", mfa_required=True)
    resp = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "mfa@once.dev", "password": STRONG_PWD},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "mfa_required"


# ---------------------------------------------------------------------------
# 6. Refresh rotates tokens
# ---------------------------------------------------------------------------


async def test_refresh_rotates_tokens(cockpit_client: AsyncClient, async_session: AsyncSession) -> None:
    await _seed_operator(email="rot@once.dev")
    login = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "rot@once.dev", "password": STRONG_PWD},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    rolled = await cockpit_client.post(
        "/cockpit/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert rolled.status_code == 200, rolled.text
    new_refresh = rolled.json()["refresh_token"]
    assert new_refresh != refresh_token


# ---------------------------------------------------------------------------
# 7. Re-using a revoked refresh token fails
# ---------------------------------------------------------------------------


async def test_revoked_refresh_cannot_be_reused(cockpit_client: AsyncClient) -> None:
    await _seed_operator(email="rev@once.dev")
    login = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "rev@once.dev", "password": STRONG_PWD},
    )
    refresh_token = login.json()["refresh_token"]
    rolled = await cockpit_client.post(
        "/cockpit/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert rolled.status_code == 200
    # First refresh token is now revoked.
    reused = await cockpit_client.post(
        "/cockpit/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reused.status_code == 401
    assert reused.json()["detail"]["code"] == "invalid_refresh"


# ---------------------------------------------------------------------------
# 8. decode_token rejects wrong token type
# ---------------------------------------------------------------------------


async def test_decode_token_rejects_wrong_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolated_env(monkeypatch)
    op = Operator(id="op1", email="x@once.dev", hashed_password="x", role="founder")
    access, _ = operator_auth.create_access_token(op)
    with pytest.raises(operator_auth.OperatorAuthError) as exc:
        operator_auth.decode_token(access, expected_type=operator_auth.TOKEN_TYPE_REFRESH)
    assert exc.value.code == "invalid_token_type"


# ---------------------------------------------------------------------------
# 9. decode_token rejects tampered token
# ---------------------------------------------------------------------------


async def test_decode_token_rejects_tampered_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolated_env(monkeypatch)
    op = Operator(id="op2", email="y@once.dev", hashed_password="x", role="founder")
    access, _ = operator_auth.create_access_token(op)
    tampered = access[:-4] + ("AAAA" if not access.endswith("AAAA") else "BBBB")
    with pytest.raises(operator_auth.OperatorAuthError) as exc:
        operator_auth.decode_token(tampered)
    assert exc.value.code == "invalid_token"


# ---------------------------------------------------------------------------
# 10. Cockpit secret is isolated from tenant secret
# ---------------------------------------------------------------------------


async def test_cockpit_secret_isolated_from_tenant_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolated_env(monkeypatch)
    op = Operator(id="op3", email="z@once.dev", hashed_password="x", role="founder")
    access, _ = operator_auth.create_access_token(op)

    # Switch env to a *different* secret; decode must now fail.
    monkeypatch.setattr(settings, "cockpit_jwt_secret_key", "totally-different-secret-" + "z" * 32)
    with pytest.raises(operator_auth.OperatorAuthError) as exc:
        operator_auth.decode_token(access)
    assert exc.value.code == "invalid_token"


# ---------------------------------------------------------------------------
# 11. /cockpit/auth/me returns the current operator profile
# ---------------------------------------------------------------------------


async def test_me_endpoint_returns_profile(cockpit_client: AsyncClient) -> None:
    await _seed_operator(email="me@once.dev", role=OperatorRole.FOUNDER.value)
    login = await cockpit_client.post(
        "/cockpit/auth/login",
        json={"email": "me@once.dev", "password": STRONG_PWD},
    )
    access = login.json()["access_token"]
    resp = await cockpit_client.get(
        "/cockpit/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "me@once.dev"
    assert body["role"] == "founder"
    assert body["all_tenants"] is True
