"""Tests for the email verification service: hashing, expiry, rate
limit, attempt cap, replay protection."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import EmailVerification
from app.services import email_verification_service as svc

pytestmark = pytest.mark.asyncio


async def test_hash_code_is_deterministic() -> None:
    assert svc.hash_code("123456") == svc.hash_code("123456")
    assert svc.hash_code("123456") != svc.hash_code("123457")


async def test_hash_code_not_plaintext() -> None:
    h = svc.hash_code("987654")
    assert "987654" not in h
    assert len(h) == 64  # sha256 hex


async def test_issue_code_persists_hash_only(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(
        async_session, email="user@example.com", tenant_id=None
    )
    record = await async_session.get(EmailVerification, issued.record_id)
    assert record is not None
    assert record.code_hash != issued.code
    assert record.code_hash == svc.hash_code(issued.code)
    assert record.consumed_at is None


async def test_issue_code_length_six(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(async_session, email="x@example.com", tenant_id=None)
    assert len(issued.code) == 6
    assert issued.code.isdigit()


async def test_verify_correct_code(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(
        async_session, email="ok@example.com", tenant_id=None
    )
    record = await svc.verify_code(
        async_session,
        email="ok@example.com",
        tenant_id=None,
        submitted_code=issued.code,
    )
    assert record.consumed_at is not None


async def test_verify_wrong_code_increments_attempts(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(
        async_session, email="wrong@example.com", tenant_id=None
    )
    with pytest.raises(Exception):
        await svc.verify_code(
            async_session,
            email="wrong@example.com",
            tenant_id=None,
            submitted_code="000000",
        )
    record = await async_session.get(EmailVerification, issued.record_id)
    assert record is not None
    assert record.attempts == 1
    assert record.consumed_at is None


async def test_verify_expired_code(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    issued = await svc.issue_code(
        async_session, email="exp@example.com", tenant_id=None
    )
    # Force the record to be expired.
    record = await async_session.get(EmailVerification, issued.record_id)
    assert record is not None
    record.expires_at = record.expires_at - timedelta(hours=2)
    await async_session.flush()
    with pytest.raises(Exception):
        await svc.verify_code(
            async_session,
            email="exp@example.com",
            tenant_id=None,
            submitted_code=issued.code,
        )


async def test_verify_replay_rejected(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(
        async_session, email="replay@example.com", tenant_id=None
    )
    await svc.verify_code(
        async_session,
        email="replay@example.com",
        tenant_id=None,
        submitted_code=issued.code,
    )
    with pytest.raises(Exception):
        await svc.verify_code(
            async_session,
            email="replay@example.com",
            tenant_id=None,
            submitted_code=issued.code,
        )


async def test_attempt_limit_enforced(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_verification_max_attempts", 2)
    issued = await svc.issue_code(
        async_session, email="cap@example.com", tenant_id=None
    )
    for _ in range(2):
        with pytest.raises(Exception):
            await svc.verify_code(
                async_session,
                email="cap@example.com",
                tenant_id=None,
                submitted_code="000000",
            )
    # Next attempt should be rate-limited (429), not a generic invalid.
    with pytest.raises(Exception) as info:
        await svc.verify_code(
            async_session,
            email="cap@example.com",
            tenant_id=None,
            submitted_code=issued.code,
        )
    assert "429" in repr(info.value) or "exhausted" in repr(info.value).lower()


async def test_rate_limit_codes_per_hour(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_verification_max_codes_per_hour", 2)
    await svc.issue_code(async_session, email="rl@example.com", tenant_id=None)
    await svc.issue_code(async_session, email="rl@example.com", tenant_id=None)
    with pytest.raises(Exception):
        await svc.issue_code(async_session, email="rl@example.com", tenant_id=None)


async def test_email_normalized_to_lowercase(async_session: AsyncSession) -> None:
    issued = await svc.issue_code(
        async_session, email="Mixed@Example.COM", tenant_id=None
    )
    record = await svc.verify_code(
        async_session,
        email="mixed@example.com",
        tenant_id=None,
        submitted_code=issued.code,
    )
    assert record.email == "mixed@example.com"
    _ = issued
