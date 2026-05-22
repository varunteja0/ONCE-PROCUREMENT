"""L3.10 — Audit-trail chain verification.

The verifier replays the chain from a starting row's ``prev_hash`` and
recomputes each ``this_hash`` for the configured tenant. Any mismatch
or gap is reported as an :class:`AuditChainBreak`. A clean replay
returns ``valid=True`` and an empty breaks list.

The replay is purely functional — it never writes to the database.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLogEntry
from app.schemas.audit import AuditChainBreak, AuditChainVerifyResult
from app.services.audit_logger import (
    canonicalise_core,
    compute_chain_hash,
    genesis_hash,
)
from app.utils.logging import get_logger

__all__ = ["verify_chain"]


_logger = get_logger(__name__)


async def verify_chain(
    session: AsyncSession,
    *,
    tenant_id: str,
    from_position: int = 1,
    to_position: int | None = None,
) -> AuditChainVerifyResult:
    """Replay the chain for *tenant_id* between the two inclusive positions.

    Returns a fully-populated :class:`AuditChainVerifyResult` — never raises
    on tamper. ``valid`` is True iff zero breaks were detected AND the
    requested window was contiguous.
    """

    stmt = (
        select(AuditLogEntry)
        .where(AuditLogEntry.tenant_id == tenant_id)
        .where(AuditLogEntry.chain_position >= from_position)
    )
    if to_position is not None:
        stmt = stmt.where(AuditLogEntry.chain_position <= to_position)
    stmt = stmt.order_by(AuditLogEntry.chain_position.asc())

    rows = list((await session.execute(stmt)).scalars().all())

    breaks: list[AuditChainBreak] = []
    expected_prev: str
    if from_position <= 1:
        expected_prev = genesis_hash(tenant_id)
    else:
        prev_stmt = (
            select(AuditLogEntry.this_hash, AuditLogEntry.chain_position)
            .where(AuditLogEntry.tenant_id == tenant_id)
            .where(AuditLogEntry.chain_position < from_position)
            .order_by(AuditLogEntry.chain_position.desc())
            .limit(1)
        )
        prev_row = (await session.execute(prev_stmt)).first()
        expected_prev = (
            str(prev_row[0]) if prev_row is not None else genesis_hash(tenant_id)
        )

    expected_position = from_position
    rows_checked = 0
    last_position = from_position - 1

    for row in rows:
        rows_checked += 1
        last_position = int(row.chain_position)
        # Detect position gap before per-row checks so the break report
        # carries the missing positions explicitly.
        if int(row.chain_position) != expected_position:
            breaks.append(
                AuditChainBreak(
                    chain_position=int(row.chain_position),
                    row_id=row.id,
                    expected_prev_hash=expected_prev,
                    actual_prev_hash=row.prev_hash,
                    expected_this_hash="",
                    actual_this_hash=row.this_hash,
                    reason="position_gap",
                )
            )
            # Re-sync — continue with the actual prev so downstream rows
            # are still checked.
            expected_prev = row.this_hash
            expected_position = int(row.chain_position) + 1
            continue

        if row.prev_hash != expected_prev:
            breaks.append(
                AuditChainBreak(
                    chain_position=int(row.chain_position),
                    row_id=row.id,
                    expected_prev_hash=expected_prev,
                    actual_prev_hash=row.prev_hash,
                    expected_this_hash="",
                    actual_this_hash=row.this_hash,
                    reason="prev_hash_mismatch",
                )
            )

        core = canonicalise_core(
            row_id=row.id,
            tenant_id=row.tenant_id,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            action_verb=row.action_verb,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            occurred_at=row.occurred_at,
            payload_summary=row.payload_summary,
            request_id=row.request_id,
        )
        recomputed = compute_chain_hash(row.prev_hash, core)
        if recomputed != row.this_hash:
            breaks.append(
                AuditChainBreak(
                    chain_position=int(row.chain_position),
                    row_id=row.id,
                    expected_prev_hash=expected_prev,
                    actual_prev_hash=row.prev_hash,
                    expected_this_hash=recomputed,
                    actual_this_hash=row.this_hash,
                    reason="this_hash_mismatch",
                )
            )

        expected_prev = row.this_hash
        expected_position = int(row.chain_position) + 1

    valid = not breaks

    _logger.info(
        "audit_chain_verified",
        tenant_id=tenant_id,
        from_position=from_position,
        to_position=to_position or last_position,
        rows_checked=rows_checked,
        breaks=len(breaks),
        valid=valid,
    )

    return AuditChainVerifyResult(
        valid=valid,
        tenant_id=tenant_id,
        rows_checked=rows_checked,
        from_position=from_position,
        to_position=to_position if to_position is not None else last_position,
        breaks=breaks,
    )
