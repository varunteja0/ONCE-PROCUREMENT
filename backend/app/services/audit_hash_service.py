"""Audit hash chain service — tamper-evident SOC 2 evidence.

For each tenant, the nightly Celery task computes a per-day digest of all
``audit_logs`` rows whose ``occurred_at`` falls inside the prior UTC
calendar day. The digest is SHA-256 of canonical JSON of the rows + the
previous day's digest (chain link).

A re-verification step re-computes the digest from current DB state and
compares to the stored value. Any mismatch indicates tampering.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditHashDigest, AuditLog
from app.services.audit_export_service import row_to_dict
from app.services.exceptions import OnceError
from app.utils.canonical_json import canonical_json_bytes
from app.utils.logging import get_logger

__all__ = [
    "AuditHashMismatch",
    "compute_daily_digest",
    "verify_daily_digest",
    "ensure_daily_digest",
    "previous_utc_day",
]


_logger = get_logger(__name__)


class AuditHashMismatch(OnceError):
    """Recomputed digest does not match the stored value — tampering."""


def previous_utc_day(now: datetime | None = None) -> date:
    """Return the calendar date of the prior UTC day (default reference: now)."""

    if now is None:
        now = datetime.now(tz=UTC)
    return (now.astimezone(UTC) - timedelta(days=1)).date()


def _day_window(day_utc: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day_utc, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


async def _load_day_rows(
    session: AsyncSession, *, tenant_id: str, day_utc: date
) -> Sequence[AuditLog]:
    start, end = _day_window(day_utc)
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .where(AuditLog.occurred_at >= start)
        .where(AuditLog.occurred_at < end)
        .order_by(AuditLog.occurred_at.asc(), AuditLog.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _prev_digest_for(
    session: AsyncSession, *, tenant_id: str, day_utc: date
) -> str:
    prev_day = day_utc - timedelta(days=1)
    prev_start, _ = _day_window(prev_day)
    stmt = (
        select(AuditHashDigest.digest_sha256)
        .where(AuditHashDigest.tenant_id == tenant_id)
        .where(AuditHashDigest.covers_date == prev_start)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() or ""


def _digest_rows(rows: Sequence[AuditLog], *, prev_digest: str) -> str:
    """SHA-256 hex of canonical JSON of (prev_digest, rows-as-dicts)."""

    payload = {
        "prev": prev_digest,
        "rows": [row_to_dict(r) for r in rows],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


async def compute_daily_digest(
    session: AsyncSession,
    *,
    tenant_id: str,
    day_utc: date,
) -> tuple[str, int, str]:
    """Compute (digest, row_count, prev_digest) for a tenant/day.

    Pure read — does **not** persist anything.
    """

    rows = await _load_day_rows(session, tenant_id=tenant_id, day_utc=day_utc)
    prev = await _prev_digest_for(session, tenant_id=tenant_id, day_utc=day_utc)
    digest = _digest_rows(rows, prev_digest=prev)
    return digest, len(rows), prev


async def ensure_daily_digest(
    session: AsyncSession,
    *,
    tenant_id: str,
    day_utc: date,
) -> AuditHashDigest:
    """Idempotently compute + persist the digest for (tenant, day_utc).

    Returns the persisted row. Safe to call repeatedly: if a row already
    exists for the (tenant, day) pair, it is returned untouched.
    """

    start, _ = _day_window(day_utc)
    existing_stmt = (
        select(AuditHashDigest)
        .where(AuditHashDigest.tenant_id == tenant_id)
        .where(AuditHashDigest.covers_date == start)
        .limit(1)
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    digest, row_count, prev = await compute_daily_digest(
        session, tenant_id=tenant_id, day_utc=day_utc
    )
    row = AuditHashDigest(
        tenant_id=tenant_id,
        covers_date=start,
        digest_sha256=digest,
        prev_digest_sha256=prev,
        row_count=row_count,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        # Race: a concurrent worker beat us. Re-read and return that row.
        await session.rollback()
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is None:
            raise
        return existing

    _logger.info(
        "audit_hash_digest_persisted",
        tenant_id=tenant_id,
        covers_date=str(day_utc),
        row_count=row_count,
        digest=digest,
    )
    return row


async def verify_daily_digest(
    session: AsyncSession,
    *,
    tenant_id: str,
    day_utc: date,
) -> AuditHashDigest:
    """Re-verify a previously-stored digest against current DB state.

    Returns the stored row on match. Raises :class:`AuditHashMismatch` when
    the recomputed digest does not match the persisted value.

    If no digest exists for (tenant, day), raises :class:`AuditHashMismatch`
    with ``context["reason"] == "missing"`` — the caller decides whether to
    treat that as failure or to lazily backfill.
    """

    start, _ = _day_window(day_utc)
    stmt = (
        select(AuditHashDigest)
        .where(AuditHashDigest.tenant_id == tenant_id)
        .where(AuditHashDigest.covers_date == start)
        .limit(1)
    )
    stored = (await session.execute(stmt)).scalar_one_or_none()
    if stored is None:
        raise AuditHashMismatch(
            "no digest recorded for tenant/day",
            tenant_id=tenant_id,
            day_utc=str(day_utc),
            reason="missing",
        )

    recomputed, row_count, prev = await compute_daily_digest(
        session, tenant_id=tenant_id, day_utc=day_utc
    )
    if recomputed != stored.digest_sha256 or prev != stored.prev_digest_sha256:
        raise AuditHashMismatch(
            "audit hash chain mismatch — tampering suspected",
            tenant_id=tenant_id,
            day_utc=str(day_utc),
            stored_digest=stored.digest_sha256,
            recomputed_digest=recomputed,
            stored_prev=stored.prev_digest_sha256,
            recomputed_prev=prev,
            row_count_now=row_count,
            row_count_at_digest=stored.row_count,
            reason="mismatch",
        )
    return stored
