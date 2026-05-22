"""Audit-log export service — SOC 2 evidence read path.

Streams ``AuditLog`` rows for a tenant within a UTC time window. The
service deliberately uses keyset-style cursor pagination on
``(occurred_at, id)`` to keep memory bounded for very large windows.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

__all__ = [
    "PAGE_SIZE",
    "iter_audit_rows",
    "count_audit_rows",
    "row_to_dict",
    "to_jsonl_bytes",
    "to_csv_bytes",
]


PAGE_SIZE: int = 500


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def count_audit_rows(
    session: AsyncSession,
    *,
    tenant_id: str,
    start: datetime,
    end: datetime,
) -> int:
    """Return the total row count for the window — for response metadata."""

    start_utc = _ensure_utc(start)
    end_utc = _ensure_utc(end)
    stmt = (
        select(func.count(AuditLog.id))
        .where(AuditLog.tenant_id == tenant_id)
        .where(AuditLog.occurred_at >= start_utc)
        .where(AuditLog.occurred_at < end_utc)
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def iter_audit_rows(
    session: AsyncSession,
    *,
    tenant_id: str,
    start: datetime,
    end: datetime,
    page_size: int = PAGE_SIZE,
) -> AsyncIterator[AuditLog]:
    """Yield ``AuditLog`` rows in deterministic ``(occurred_at, id)`` order.

    Uses keyset pagination so the export remains bounded-memory even when
    the window spans millions of rows.
    """

    start_utc = _ensure_utc(start)
    end_utc = _ensure_utc(end)

    last_at: datetime | None = None
    last_id: str | None = None

    while True:
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .where(AuditLog.occurred_at >= start_utc)
            .where(AuditLog.occurred_at < end_utc)
            .order_by(AuditLog.occurred_at.asc(), AuditLog.id.asc())
            .limit(page_size)
        )
        if last_at is not None and last_id is not None:
            stmt = stmt.where(
                or_(
                    AuditLog.occurred_at > last_at,
                    and_(
                        AuditLog.occurred_at == last_at,
                        AuditLog.id > last_id,
                    ),
                )
            )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return
        for row in rows:
            yield row
        if len(rows) < page_size:
            return
        last_at = rows[-1].occurred_at
        last_id = rows[-1].id


def row_to_dict(row: AuditLog) -> dict[str, Any]:
    """Stable serialization of an ``AuditLog`` row — used by JSONL + CSV."""

    occurred_at = row.occurred_at
    if occurred_at is not None and occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "actor_user_id": row.actor_user_id,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "metadata_json": row.metadata_json,
        "ip_address": row.ip_address,
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z")
        if occurred_at is not None
        else None,
    }


async def to_jsonl_bytes(
    session: AsyncSession,
    *,
    tenant_id: str,
    start: datetime,
    end: datetime,
) -> bytes:
    """Collect the full window into a JSON Lines byte string.

    Caller is responsible for choosing a window small enough to fit in
    memory. For Type-I evidence the typical window is one calendar
    quarter for one tenant, which comfortably fits.
    """

    buf = io.BytesIO()
    async for row in iter_audit_rows(
        session, tenant_id=tenant_id, start=start, end=end
    ):
        line = json.dumps(row_to_dict(row), separators=(",", ":"), sort_keys=True)
        buf.write(line.encode("utf-8"))
        buf.write(b"\n")
    return buf.getvalue()


_CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "tenant_id",
    "actor_user_id",
    "action",
    "resource_type",
    "resource_id",
    "ip_address",
    "occurred_at",
    "metadata_json",
)


async def to_csv_bytes(
    session: AsyncSession,
    *,
    tenant_id: str,
    start: datetime,
    end: datetime,
) -> bytes:
    """Collect the full window into a CSV byte string with a stable header."""

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    async for row in iter_audit_rows(
        session, tenant_id=tenant_id, start=start, end=end
    ):
        data = row_to_dict(row)
        writer.writerow(
            [
                data["id"] or "",
                data["tenant_id"] or "",
                data["actor_user_id"] or "",
                data["action"] or "",
                data["resource_type"] or "",
                data["resource_id"] or "",
                data["ip_address"] or "",
                data["occurred_at"] or "",
                json.dumps(data["metadata_json"], separators=(",", ":"), sort_keys=True)
                if data["metadata_json"] is not None
                else "",
            ]
        )
    return buf.getvalue().encode("utf-8")
