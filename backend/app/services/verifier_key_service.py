"""Verifier API key issuance + lookup service.

Pure functions over an :class:`AsyncSession`. No HTTP, no FastAPI imports —
per ``.github/instructions/backend-services.instructions.md``. Plaintext keys
are returned only by :func:`issue_key`; every other code path reads from the
hashed columns.

Key format::

    vk_live_<32 url-safe base64 bytes (no padding)>

The ``key_prefix`` column stores the first 16 chars (``vk_live_`` + 8 chars
of the random tail). That prefix is unique and indexed so the verifier
service can look up a candidate key without scanning the table.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VerifierApiKey
from app.models.verifier_api_key_usage import VerifierApiKeyUsage
from app.services.exceptions import OnceError
from app.utils.logging import get_logger

__all__ = [
    "issue_key",
    "list_keys",
    "get_key",
    "revoke_key",
    "find_active_by_prefix",
    "verify_plaintext",
    "touch_last_used",
    "charge_usage",
    "ChargeResult",
    "IssuedKey",
    "KEY_PLAINTEXT_PREFIX",
    "KEY_PREFIX_LENGTH",
]


_logger = get_logger(__name__)

# Plaintext literal prefix. Distinguishes a live verifier key from any
# future key class (e.g. ``vk_test_`` for sandbox).
KEY_PLAINTEXT_PREFIX: str = "vk_live_"
# Number of plaintext characters retained as the public ``key_prefix``
# (``vk_live_`` is 8 chars + 8 chars of tail = 16).
KEY_PREFIX_LENGTH: int = 16


class IssuedKey(NamedTuple):
    row: VerifierApiKey
    plaintext: str


def _generate_plaintext() -> str:
    """Return a fresh 256-bit url-safe key with the ``vk_live_`` prefix."""

    tail = secrets.token_urlsafe(32)
    return f"{KEY_PLAINTEXT_PREFIX}{tail}"


def _hash_plaintext(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _prefix_of(plaintext: str) -> str:
    return plaintext[:KEY_PREFIX_LENGTH]


async def issue_key(
    session: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    monthly_call_cap: int | None,
    operator_id: str | None = None,
) -> IssuedKey:
    """Mint a new key and persist its hash. Plaintext is returned ONCE."""

    name_clean = name.strip()
    if not name_clean:
        raise OnceError("invalid_key_name", name=name)

    plaintext = _generate_plaintext()
    row = VerifierApiKey(
        tenant_id=tenant_id,
        name=name_clean,
        key_prefix=_prefix_of(plaintext),
        key_hash=_hash_plaintext(plaintext),
        monthly_call_cap=monthly_call_cap,
        created_by_operator_id=operator_id,
    )
    session.add(row)
    await session.flush()
    _logger.info(
        "verifier_api_key_issued",
        verifier_api_key_id=row.id,
        tenant_id=tenant_id,
        key_prefix=row.key_prefix,
        monthly_call_cap=monthly_call_cap,
        created_by_operator_id=operator_id,
    )
    return IssuedKey(row=row, plaintext=plaintext)


async def list_keys(session: AsyncSession, *, tenant_id: str) -> tuple[int, list[VerifierApiKey]]:
    total = int(
        (
            await session.execute(select(func.count(VerifierApiKey.id)).where(VerifierApiKey.tenant_id == tenant_id))
        ).scalar_one()
        or 0
    )
    rows = list(
        (
            await session.execute(
                select(VerifierApiKey)
                .where(VerifierApiKey.tenant_id == tenant_id)
                .order_by(desc(VerifierApiKey.created_at))
            )
        )
        .scalars()
        .all()
    )
    return total, rows


async def get_key(session: AsyncSession, *, tenant_id: str, key_id: str) -> VerifierApiKey | None:
    result = await session.execute(
        select(VerifierApiKey).where(
            VerifierApiKey.id == key_id,
            VerifierApiKey.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def revoke_key(
    session: AsyncSession,
    *,
    tenant_id: str,
    key_id: str,
) -> VerifierApiKey | None:
    """Mark a key revoked. Idempotent — already-revoked rows are returned as-is."""

    row = await get_key(session, tenant_id=tenant_id, key_id=key_id)
    if row is None:
        return None
    if row.revoked_at is None:
        row.revoked_at = datetime.now(tz=UTC)
        await session.flush()
        _logger.info(
            "verifier_api_key_revoked",
            verifier_api_key_id=row.id,
            tenant_id=tenant_id,
            key_prefix=row.key_prefix,
        )
    return row


async def find_active_by_prefix(session: AsyncSession, *, prefix: str) -> VerifierApiKey | None:
    """Look up an unrevoked key by its public prefix. Cross-tenant."""

    result = await session.execute(
        select(VerifierApiKey).where(
            VerifierApiKey.key_prefix == prefix,
            VerifierApiKey.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _find_active_by_prefix_for_update(session: AsyncSession, *, prefix: str) -> VerifierApiKey | None:
    """Look up an unrevoked key and lock it for a usage-counter update."""

    result = await session.execute(
        select(VerifierApiKey)
        .where(
            VerifierApiKey.key_prefix == prefix,
            VerifierApiKey.revoked_at.is_(None),
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


def verify_plaintext(row: VerifierApiKey, plaintext: str) -> bool:
    """Constant-time compare of a candidate plaintext against the stored hash."""

    candidate = _hash_plaintext(plaintext)
    return hmac.compare_digest(candidate, row.key_hash)


async def touch_last_used(session: AsyncSession, *, row: VerifierApiKey) -> None:
    """Bump ``last_used_at`` to now. Best-effort; caller commits."""

    row.last_used_at = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Usage counter ("charge" = authenticate + increment monthly counter)
# ---------------------------------------------------------------------------


def _period_month_now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")


class ChargeResult(NamedTuple):
    status: str  # "ok" | "invalid_key" | "quota_exceeded"
    api_key_id: str | None
    tenant_id: str | None
    monthly_call_cap: int | None
    current_period_count: int
    period_month: str


async def charge_usage(
    session: AsyncSession,
    *,
    plaintext: str,
) -> ChargeResult:
    """Authenticate a plaintext key and atomically increment its monthly counter.

    Returns a :class:`ChargeResult` whose ``status`` is one of:

    * ``"invalid_key"`` — prefix not found OR hash mismatch OR revoked.
      Caller should map to HTTP 401.
    * ``"quota_exceeded"`` — authenticated but ``monthly_call_cap`` reached.
      The counter is *still incremented* (so the caller sees the same total
      on a retry); caller should map to HTTP 402.
    * ``"ok"`` — authenticated and under cap.

    The function commits no transaction itself — caller is responsible.
    """

    period = _period_month_now()
    prefix = plaintext[:KEY_PREFIX_LENGTH]
    row = await _find_active_by_prefix_for_update(session, prefix=prefix)
    if row is None or not verify_plaintext(row, plaintext):
        return ChargeResult(
            status="invalid_key",
            api_key_id=None,
            tenant_id=None,
            monthly_call_cap=None,
            current_period_count=0,
            period_month=period,
        )

    usage = (
        await session.execute(
            select(VerifierApiKeyUsage).where(
                VerifierApiKeyUsage.api_key_id == row.id,
                VerifierApiKeyUsage.period_month == period,
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        usage = VerifierApiKeyUsage(api_key_id=row.id, period_month=period, count=1)
        session.add(usage)
    else:
        usage.count += 1
    await session.flush()

    await touch_last_used(session, row=row)

    cap = row.monthly_call_cap
    new_count = usage.count
    if cap is not None and new_count > cap:
        _logger.info(
            "verifier_api_key_quota_exceeded",
            verifier_api_key_id=row.id,
            tenant_id=row.tenant_id,
            count=new_count,
            cap=cap,
            period_month=period,
        )
        return ChargeResult(
            status="quota_exceeded",
            api_key_id=row.id,
            tenant_id=row.tenant_id,
            monthly_call_cap=cap,
            current_period_count=new_count,
            period_month=period,
        )

    return ChargeResult(
        status="ok",
        api_key_id=row.id,
        tenant_id=row.tenant_id,
        monthly_call_cap=cap,
        current_period_count=new_count,
        period_month=period,
    )
