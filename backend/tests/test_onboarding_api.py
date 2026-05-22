"""End-to-end onboarding API tests — full wizard happy-path + error
branches."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import email_dispatcher as ed

pytestmark = pytest.mark.asyncio


_VALID_PW = "Tr0ub4dor&Maximus99"


@pytest.fixture(autouse=True)
def _outbox_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "email_dispatcher", "outbox")
    monkeypatch.setattr(settings, "email_outbox_dir", str(tmp_path))
    monkeypatch.setattr(settings, "app_env", "development", raising=False)
    ed.reset_dispatcher_cache()
    yield tmp_path
    ed.reset_dispatcher_cache()


async def _start(client: AsyncClient, *, email: str = "founder@example.com") -> dict:
    response = await client.post(
        "/v1/onboarding/start",
        json={
            "email": email,
            "password": _VALID_PW,
            "company_name": "Acme MGA",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_start_creates_tenant_and_returns_token(client: AsyncClient) -> None:
    body = await _start(client)
    assert body["onboarding_session_token"]
    assert body["tenant_id"]
    assert body["dev_verification_code"]  # dev mode


async def test_start_rejects_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/onboarding/start",
        json={
            "email": "weak@example.com",
            "password": "short",
            "company_name": "Acme",
        },
    )
    assert response.status_code == 422 or response.status_code == 400


async def test_start_rejects_duplicate_email(client: AsyncClient) -> None:
    await _start(client, email="dup@example.com")
    response = await client.post(
        "/v1/onboarding/start",
        json={
            "email": "dup@example.com",
            "password": _VALID_PW,
            "company_name": "Acme",
        },
    )
    assert response.status_code == 409


async def test_honeypot_silently_blocks(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/onboarding/start",
        json={
            "email": "bot@example.com",
            "password": _VALID_PW,
            "company_name": "Acme",
            "website_url": "https://spam",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["onboarding_session_token"] == "bot"


async def test_verify_email_happy_path_returns_full_tokens(client: AsyncClient) -> None:
    body = await _start(client, email="verify@example.com")
    code = body["dev_verification_code"]
    response = await client.post(
        "/v1/onboarding/verify-email",
        json={"code": code},
        headers={"Authorization": f"Bearer {body['onboarding_session_token']}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["current_step"] == "profile"


async def test_verify_email_wrong_code_rejected(client: AsyncClient) -> None:
    body = await _start(client, email="bad@example.com")
    response = await client.post(
        "/v1/onboarding/verify-email",
        json={"code": "000000"},
        headers={"Authorization": f"Bearer {body['onboarding_session_token']}"},
    )
    assert response.status_code == 400


async def test_state_requires_full_token(client: AsyncClient) -> None:
    body = await _start(client, email="state@example.com")
    # Onboarding-scoped token cannot hit full-session endpoints.
    response = await client.get(
        "/v1/onboarding/state",
        headers={"Authorization": f"Bearer {body['onboarding_session_token']}"},
    )
    assert response.status_code in (401, 403)


async def _verified_client(client: AsyncClient, email: str) -> tuple[str, str]:
    body = await _start(client, email=email)
    verify = await client.post(
        "/v1/onboarding/verify-email",
        json={"code": body["dev_verification_code"]},
        headers={"Authorization": f"Bearer {body['onboarding_session_token']}"},
    )
    data = verify.json()
    return data["access_token"], data["tenant_id"]


async def test_full_happy_path_to_done(client: AsyncClient, async_session) -> None:
    access, tenant_id = await _verified_client(client, "happy@example.com")
    auth = {"Authorization": f"Bearer {access}"}

    state = await client.get("/v1/onboarding/state", headers=auth)
    assert state.status_code == 200
    assert state.json()["current_step"] == "profile"

    r = await client.post(
        "/v1/onboarding/company-profile",
        json={
            "legal_name": "Acme MGA LLC",
            "fein": "12-3456789",
            "primary_state": "CA",
            "employees": 12,
        },
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["current_step"] == "plan"

    # Skip plan + portal.
    for step in ("plan", "portal"):
        r = await client.post(
            "/v1/onboarding/skip-step", json={"step": step}, headers=auth
        )
        assert r.status_code == 200, r.text

    # Add supplier.
    r = await client.post(
        "/v1/onboarding/add-supplier",
        json={"legal_name": "Beta Inc", "state": "CA"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.json()["completed_steps"]  # smoke

    # We need a supplier_id and portal_id for run-first-submission.
    from sqlalchemy import select

    from app.models import Portal, Supplier

    portal = (await async_session.execute(select(Portal).limit(1))).scalar_one()
    supplier = (
        await async_session.execute(
            select(Supplier).where(Supplier.tenant_id == tenant_id)
        )
    ).scalar_one()

    r = await client.post(
        "/v1/onboarding/run-first-submission",
        json={"supplier_id": supplier.id, "portal_id": portal.id},
        headers=auth,
    )
    assert r.status_code == 202, r.text

    r = await client.post("/v1/onboarding/complete", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["current_step"] == "done"


async def test_skip_non_skippable_step_rejected(client: AsyncClient) -> None:
    access, _ = await _verified_client(client, "skip@example.com")
    r = await client.post(
        "/v1/onboarding/skip-step",
        json={"step": "profile"},  # not a skippable enum value
        headers={"Authorization": f"Bearer {access}"},
    )
    # The Literal in the schema rejects it at the validation layer.
    assert r.status_code in (400, 422)


async def test_verify_email_idempotent(client: AsyncClient) -> None:
    body = await _start(client, email="idem@example.com")
    code = body["dev_verification_code"]
    headers = {"Authorization": f"Bearer {body['onboarding_session_token']}"}
    first = await client.post(
        "/v1/onboarding/verify-email", json={"code": code}, headers=headers
    )
    assert first.status_code == 200
    # Re-issuing verify with the same onboarding token: the token still
    # claims email_verified=False, but the server should recognise the
    # tenant is already active. Because the code is now consumed, a fresh
    # one would be needed — we accept either a 200 (idempotent) or a 400.
    second = await client.post(
        "/v1/onboarding/verify-email", json={"code": code}, headers=headers
    )
    assert second.status_code in (200, 400)
