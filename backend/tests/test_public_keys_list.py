"""Tests for the public ``/v1/public/keys`` list endpoint.

Verifies:

* The endpoint requires no auth.
* It returns every registered key (active + revoked) by default.
* ``include_revoked=false`` filters to active only.
* The ``.txt`` variant emits one ``key_id`` header + PEM block per active key.
* Both responses set ``Cache-Control: public, max-age=3600``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signing_key import SigningKey


def _public_pem() -> str:
    return (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


async def _seed_keys(session: AsyncSession) -> tuple[str, str]:
    active = SigningKey(
        id="active-key",
        algorithm="ed25519",
        public_key_pem=_public_pem(),
        description="current",
    )
    revoked = SigningKey(
        id="revoked-key",
        algorithm="ed25519",
        public_key_pem=_public_pem(),
        description="prior",
        revoked_at=datetime.now(UTC) - timedelta(days=1),
    )
    session.add_all([active, revoked])
    await session.commit()
    return active.id, revoked.id


@pytest.mark.asyncio
async def test_list_public_keys_returns_all_by_default(client: AsyncClient, async_session: AsyncSession) -> None:
    active_id, revoked_id = await _seed_keys(async_session)

    response = await client.get("/v1/public/keys")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    ids = {row["key_id"] for row in payload["keys"]}
    assert ids == {active_id, revoked_id}
    statuses = {row["key_id"]: row["status"] for row in payload["keys"]}
    assert statuses[active_id] == "active"
    assert statuses[revoked_id] == "revoked"
    assert response.headers["Cache-Control"] == "public, max-age=3600"


@pytest.mark.asyncio
async def test_list_public_keys_filters_revoked(client: AsyncClient, async_session: AsyncSession) -> None:
    active_id, _ = await _seed_keys(async_session)

    response = await client.get("/v1/public/keys", params={"include_revoked": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["keys"][0]["key_id"] == active_id


@pytest.mark.asyncio
async def test_list_public_keys_txt_emits_pem_blocks(client: AsyncClient, async_session: AsyncSession) -> None:
    active_id, _ = await _seed_keys(async_session)

    response = await client.get("/v1/public/keys.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    body = response.text
    assert f"key_id: {active_id}" in body
    assert "BEGIN PUBLIC KEY" in body
    # Revoked keys are excluded from the DNS-publishable view.
    assert "revoked-key" not in body


@pytest.mark.asyncio
async def test_list_public_keys_requires_no_auth(client: AsyncClient) -> None:
    response = await client.get("/v1/public/keys")
    assert response.status_code == 200
