"""Tenant-scoped read service for ConsentRecord rows."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsentRecord
from app.services.exceptions import OnceError

__all__ = [
    "NotFoundError",
    "get",
    "list_consents",
]

_MAX_LIMIT = 200


class NotFoundError(OnceError):
    """The requested consent record does not exist for this tenant."""


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_LIMIT))


async def list_consents(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str | None = None,
    portal_id: str | None = None,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ConsentRecord], int]:
    """List consent records for a tenant.

    ``portal_id`` filters to consents whose ``portal_ids_json`` list either
    contains the given portal id or the wildcard ``"*"``. The filter is
    applied in Python after the SQL fetch to keep the schema SQLite-portable
    (no JSON containment operators).
    """

    limit = _clamp_limit(limit)
    offset = max(0, offset)
    stmt = select(ConsentRecord).where(ConsentRecord.tenant_id == tenant_id)
    count_stmt = select(func.count(ConsentRecord.id)).where(ConsentRecord.tenant_id == tenant_id)
    if supplier_id is not None:
        stmt = stmt.where(ConsentRecord.supplier_id == supplier_id)
        count_stmt = count_stmt.where(ConsentRecord.supplier_id == supplier_id)
    if active_only:
        stmt = stmt.where(ConsentRecord.revoked_at.is_(None))
        count_stmt = count_stmt.where(ConsentRecord.revoked_at.is_(None))
    stmt = stmt.order_by(ConsentRecord.granted_at.desc(), ConsentRecord.id.desc())

    if portal_id is not None:
        # Portal filter happens in Python because ``portal_ids_json`` is a
        # generic JSON column and SQLite has no first-class containment op.
        # We page in Python too so totals stay consistent with the filter.
        items_result = await session.execute(stmt)
        all_rows = list(items_result.scalars().all())
        filtered = [
            row for row in all_rows if portal_id in (row.portal_ids_json or []) or "*" in (row.portal_ids_json or [])
        ]
        total = len(filtered)
        page = filtered[offset : offset + limit]
        return page, total

    stmt = stmt.limit(limit).offset(offset)
    items_result = await session.execute(stmt)
    total_result = await session.execute(count_stmt)
    return list(items_result.scalars().all()), int(total_result.scalar_one() or 0)


async def get(
    session: AsyncSession,
    *,
    tenant_id: str,
    consent_id: str,
) -> ConsentRecord:
    stmt = select(ConsentRecord).where(
        ConsentRecord.id == consent_id,
        ConsentRecord.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            "consent record not found",
            consent_id=consent_id,
            tenant_id=tenant_id,
        )
    return row
