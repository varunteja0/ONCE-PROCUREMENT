"""L3.6 — Email verification service.

Responsibilities:

* Issue 6-digit codes, stored as ``sha256(code + pepper)``.
* Enforce rate limits (``EMAIL_VERIFICATION_MAX_CODES_PER_HOUR``).
* Enforce per-code attempt cap (``EMAIL_VERIFICATION_MAX_ATTEMPTS``).
* Constant-time comparison of submitted code vs stored hash.
* Reject expired / consumed / replayed codes.

Codes are tied to ``(email, tenant_id)``. ``tenant_id`` may be ``None``
for pre-tenant flows but in the onboarding wizard we always have one.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import EmailVerification
from app.utils.logging import get_logger

__all__ = [
    "IssuedCode",
    "issue_code",
    "verify_code",
    "hash_code",
    "CODE_LENGTH",
]


_logger = get_logger(__name__)

CODE_LENGTH: int = 6


@dataclass(slots=True)
class IssuedCode:
    record_id: str
    code: str  # plaintext — never persist; return to caller for delivery
    expires_at: datetime


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; treat naive timestamps as UTC for safe compares."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _pepper() -> str:
    return settings.secret_key or "once-pepper"


def hash_code(code: str) -> str:
    """Return ``hex(sha256(code + pepper))``."""

    if not isinstance(code, str) or not code:
        raise ValueError("code must be a non-empty string")
    return hashlib.sha256((code + _pepper()).encode("utf-8")).hexdigest()


def _generate_numeric_code(length: int = CODE_LENGTH) -> str:
    # Use ``secrets`` for cryptographic randomness.
    upper = 10**length
    n = secrets.randbelow(upper)
    return f"{n:0{length}d}"


async def _count_codes_in_last_hour(
    session: AsyncSession, *, email: str
) -> int:
    cutoff = _utcnow() - timedelta(hours=1)
    stmt = (
        select(func.count(EmailVerification.id))
        .where(EmailVerification.email == email)
        .where(EmailVerification.created_at >= cutoff)
    )
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


async def issue_code(
    session: AsyncSession,
    *,
    email: str,
    tenant_id: str | None,
    ip_address: str | None = None,
) -> IssuedCode:
    """Issue a new verification code for ``email``.

    Raises HTTP 429 if more than ``max_codes_per_hour`` have been issued.
    """

    normalized = email.strip().lower()
    recent = await _count_codes_in_last_hour(session, email=normalized)
    if recent >= settings.email_verification_max_codes_per_hour:
        _logger.warning(
            "email_verification_rate_limit", email=normalized, recent=recent
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "email_verification_rate_limited",
                "message": "Too many verification codes requested. Try again in an hour.",
            },
        )

    code = _generate_numeric_code()
    record = EmailVerification(
        tenant_id=tenant_id,
        email=normalized,
        code_hash=hash_code(code),
        expires_at=_utcnow()
        + timedelta(minutes=settings.email_verification_code_ttl_minutes),
        attempts=0,
        ip_address=ip_address,
    )
    session.add(record)
    await session.flush()
    _logger.info(
        "email_verification_issued",
        email=normalized,
        tenant_id=tenant_id,
        record_id=record.id,
    )
    return IssuedCode(record_id=record.id, code=code, expires_at=record.expires_at)


async def _latest_unconsumed(
    session: AsyncSession, *, email: str, tenant_id: str | None
) -> EmailVerification | None:
    stmt = (
        select(EmailVerification)
        .where(EmailVerification.email == email)
        .where(EmailVerification.consumed_at.is_(None))
    )
    if tenant_id is not None:
        stmt = stmt.where(EmailVerification.tenant_id == tenant_id)
    stmt = stmt.order_by(desc(EmailVerification.created_at)).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def verify_code(
    session: AsyncSession,
    *,
    email: str,
    tenant_id: str | None,
    submitted_code: str,
) -> EmailVerification:
    """Verify ``submitted_code`` against the latest active code for ``email``.

    Raises HTTP 400 ``invalid_or_expired_code`` on mismatch / expiry /
    exhausted attempts.
    """

    normalized = email.strip().lower()
    record = await _latest_unconsumed(session, email=normalized, tenant_id=tenant_id)

    invalid_exc = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invalid_or_expired_code",
            "message": "The verification code is invalid or has expired.",
        },
    )

    if record is None:
        raise invalid_exc

    if _aware(record.expires_at) <= _utcnow():
        raise invalid_exc

    if record.attempts >= settings.email_verification_max_attempts:
        _logger.warning(
            "email_verification_attempts_exceeded",
            email=normalized,
            record_id=record.id,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "verification_attempts_exhausted",
                "message": "Too many incorrect attempts. Request a new code.",
            },
        )

    record.attempts = record.attempts + 1

    expected = record.code_hash
    submitted = hash_code(submitted_code.strip())
    if not hmac.compare_digest(expected, submitted):
        await session.flush()
        raise invalid_exc

    record.consumed_at = _utcnow()
    await session.flush()
    _logger.info(
        "email_verification_consumed",
        email=normalized,
        tenant_id=tenant_id,
        record_id=record.id,
    )
    return record
