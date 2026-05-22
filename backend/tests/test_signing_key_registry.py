"""Tests for ``app.services.receipt_signer`` key-registry helpers.

Covers:

* ``bootstrap_signing_key`` is idempotent and populates the in-process cache
* ``load_signing_key_into_cache`` returns the PEM and memoizes it
* ``load_signing_key_into_cache`` falls back to the env-derived PEM when the
  row is missing
* a revoked key row falls back to the env-derived PEM (or None)
* ``clear_public_key_cache`` resets the cache
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from app.config import settings
from app.models import SigningKey
from app.services import receipt_signer
from app.services.receipt_signer import (
    bootstrap_signing_key,
    clear_public_key_cache,
    get_public_key_pem,
    load_signing_key_into_cache,
)

pytestmark = pytest.mark.asyncio


def _pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


class TestBootstrap:
    async def test_bootstrap_inserts_row_when_pem_configured(
        self, async_session, signing_key
    ) -> None:
        clear_public_key_cache()
        await bootstrap_signing_key(async_session)
        row = await async_session.get(SigningKey, settings.receipt_signing_key_id)
        assert row is not None
        assert row.algorithm == "ed25519"
        assert "BEGIN PUBLIC KEY" in row.public_key_pem

    async def test_bootstrap_is_idempotent(
        self, async_session, signing_key
    ) -> None:
        await bootstrap_signing_key(async_session)
        await bootstrap_signing_key(async_session)
        rows = await async_session.execute(select(SigningKey))
        assert len(list(rows.scalars().all())) == 1

    async def test_bootstrap_skipped_when_pem_blank(
        self, async_session, monkeypatch
    ) -> None:
        clear_public_key_cache()
        monkeypatch.setattr(settings, "receipt_signing_private_key_pem", "")
        await bootstrap_signing_key(async_session)
        # No row should have been added.
        rows = await async_session.execute(select(SigningKey))
        assert list(rows.scalars().all()) == []


class TestLoadAndCache:
    async def test_load_returns_pem_and_populates_cache(
        self, async_session, signing_key
    ) -> None:
        clear_public_key_cache()
        await bootstrap_signing_key(async_session)
        pem = await load_signing_key_into_cache(
            async_session, settings.receipt_signing_key_id
        )
        assert pem and "BEGIN PUBLIC KEY" in pem
        assert get_public_key_pem(settings.receipt_signing_key_id) == pem

    async def test_load_falls_back_to_env_derived_when_row_missing(
        self, async_session, signing_key
    ) -> None:
        clear_public_key_cache()
        # Don't bootstrap; row is missing.
        pem = await load_signing_key_into_cache(
            async_session, settings.receipt_signing_key_id
        )
        assert pem is not None
        assert "BEGIN PUBLIC KEY" in pem

    async def test_load_unknown_key_id_returns_none(
        self, async_session, signing_key
    ) -> None:
        clear_public_key_cache()
        pem = await load_signing_key_into_cache(
            async_session, "totally-unknown-key-id"
        )
        assert pem is None

    async def test_revoked_key_falls_back_to_env_or_none(
        self, async_session, signing_key
    ) -> None:
        clear_public_key_cache()
        # Insert a revoked row under a DIFFERENT id (not the env key id) so
        # the env fallback returns None and we exercise the revoked branch
        # purely.
        new = Ed25519PrivateKey.generate()
        async_session.add(
            SigningKey(
                id="revoked-key",
                algorithm="ed25519",
                public_key_pem=_pem(new),
                description="revoked",
                revoked_at=datetime.now(UTC),
            )
        )
        await async_session.flush()

        pem = await load_signing_key_into_cache(async_session, "revoked-key")
        assert pem is None

    async def test_clear_cache_evicts_entries(
        self, async_session, signing_key
    ) -> None:
        await bootstrap_signing_key(async_session)
        assert get_public_key_pem(settings.receipt_signing_key_id) is not None
        clear_public_key_cache()
        # After clearing, get_public_key_pem still works via env fallback.
        # But the cache dict itself is empty.
        assert receipt_signer._PUBLIC_KEY_CACHE == {}
