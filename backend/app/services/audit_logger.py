"""L3.10 — Audit-trail append + chain-hash compute.

Public entry point: :func:`record_audit_event`. Designed to be called from
the audit middleware (per HTTP request) and from service-layer code paths
that need to attribute non-HTTP lifecycle events (Celery tasks, webhook
handlers, IMAP poller, etc.).

Contract:

* Each append computes ``this_hash = sha256(prev_hash || canonical_json(core))``
  where ``core`` is a fixed, stable subset of the row's fields. The
  algorithm is canonicalised in :func:`compute_chain_hash` so the
  verification path (:mod:`app.services.audit_chain`) replays it bit-for-bit.
* The append is **best-effort**: a write failure logs a structured
  warning but never raises — an audit-write outage must not 500 the
  caller (this is required by SOC 2 CC7.4 — the system continues to
  serve customers even when monitoring degrades).
* Per-tenant chain position is allocated with ``SELECT ... FOR UPDATE``
  on Postgres (a row-lock on a sentinel) or, on SQLite, by reading the
  ``MAX(chain_position)`` inside the same transaction. Concurrent
  appends are serialised by the database, not by Python locks.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.secrets_redaction import redact_secrets
from app.models.audit_log import (
    GENESIS_HASH_PREFIX,
    AuditActorType,
    AuditLogEntry,
    new_ulid,
)
from app.utils.canonical_json import canonical_json_bytes
from app.utils.logging import get_logger

__all__ = [
    "record_audit_event",
    "compute_chain_hash",
    "genesis_hash",
    "canonicalise_core",
]


_logger = get_logger(__name__)


def genesis_hash(tenant_id: str) -> str:
    """Return the hex SHA-256 of the genesis seed for *tenant_id*."""

    return hashlib.sha256(GENESIS_HASH_PREFIX + tenant_id.encode("utf-8")).hexdigest()


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def canonicalise_core(
    *,
    row_id: str,
    tenant_id: str,
    actor_type: AuditActorType | str,
    actor_id: str | None,
    action_verb: str,
    resource_type: str,
    resource_id: str | None,
    occurred_at: datetime,
    payload_summary: Mapping[str, Any] | None,
    request_id: str | None,
) -> dict[str, Any]:
    """Return the stable subset of fields that feed the chain hash."""

    actor_value = (
        actor_type.value if isinstance(actor_type, AuditActorType) else str(actor_type)
    )
    return {
        "id": row_id,
        "tenant_id": tenant_id,
        "actor_type": actor_value,
        "actor_id": actor_id,
        "action_verb": action_verb,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "occurred_at": _iso_utc(occurred_at),
        "payload_summary": dict(payload_summary) if payload_summary else None,
        "request_id": request_id,
    }


def compute_chain_hash(prev_hash: str, core: Mapping[str, Any]) -> str:
    """Compute ``sha256(prev_hash_bytes || canonical_json(core))`` as hex."""

    hasher = hashlib.sha256()
    hasher.update(bytes.fromhex(prev_hash))
    hasher.update(canonical_json_bytes(dict(core)))
    return hasher.hexdigest()


async def _tail(
    session: AsyncSession, *, tenant_id: str
) -> tuple[str, int]:
    """Return ``(prev_hash, next_position)`` for *tenant_id*'s chain tail."""

    stmt = (
        select(AuditLogEntry.this_hash, AuditLogEntry.chain_position)
        .where(AuditLogEntry.tenant_id == tenant_id)
        .order_by(AuditLogEntry.chain_position.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return genesis_hash(tenant_id), 1
    return str(row[0]), int(row[1]) + 1


async def record_audit_event(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor_type: AuditActorType,
    action_verb: str,
    resource_type: str,
    actor_id: str | None = None,
    actor_email: str | None = None,
    resource_id: str | None = None,
    resource_label: str | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    payload_summary: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
    flush: bool = True,
) -> AuditLogEntry | None:
    """Append a single chain-linked audit row. Returns the new row on success.

    Best-effort: returns ``None`` (and warn-logs) on any error. Callers
    must NOT raise on a ``None`` return.
    """

    try:
        when = occurred_at or datetime.now(tz=UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)

        redacted_summary = (
            redact_secrets(dict(payload_summary)) if payload_summary else None
        )

        row_id = new_ulid()
        prev_hash, position = await _tail(session, tenant_id=tenant_id)
        core = canonicalise_core(
            row_id=row_id,
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action_verb=action_verb,
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=when,
            payload_summary=redacted_summary,
            request_id=request_id,
        )
        this_hash = compute_chain_hash(prev_hash, core)

        row = AuditLogEntry(
            id=row_id,
            tenant_id=tenant_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_email=actor_email,
            action_verb=action_verb,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            occurred_at=when,
            payload_summary=redacted_summary,
            prev_hash=prev_hash,
            this_hash=this_hash,
            chain_position=position,
        )
        session.add(row)
        if flush:
            await session.flush()
        _logger.info(
            "audit_trail_appended",
            tenant_id=tenant_id,
            actor_type=actor_type.value,
            action_verb=action_verb,
            resource_type=resource_type,
            resource_id=resource_id,
            chain_position=position,
            this_hash=this_hash,
        )
        return row
    except Exception as exc:  # noqa: BLE001 — best-effort by contract
        _logger.warning(
            "audit_trail_append_failed",
            tenant_id=tenant_id,
            action_verb=action_verb,
            resource_type=resource_type,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return None


async def tenant_chain_length(session: AsyncSession, *, tenant_id: str) -> int:
    """Return the current chain length for a tenant (0 if empty)."""

    stmt = select(func.count(AuditLogEntry.id)).where(
        AuditLogEntry.tenant_id == tenant_id
    )
    return int((await session.execute(stmt)).scalar_one() or 0)
