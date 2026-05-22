from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Portal
from app.utils.logging import get_logger

__all__ = ["list_portals", "count_portals", "get_portal"]


_logger = get_logger(__name__)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


def _clamp_limit(limit: int) -> int:
    if limit <= 0:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


def _apply_filters(stmt: Any, *, is_supported: bool | None) -> Any:
    if is_supported is not None:
        stmt = stmt.where(Portal.is_supported.is_(is_supported))
    return stmt


async def list_portals(
    session: AsyncSession,
    *,
    is_supported: bool | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> list[Portal]:
    stmt = select(Portal)
    stmt = _apply_filters(stmt, is_supported=is_supported)
    stmt = stmt.order_by(Portal.display_name.asc(), Portal.id.asc())
    stmt = stmt.limit(_clamp_limit(limit)).offset(max(offset, 0))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_portals(
    session: AsyncSession,
    *,
    is_supported: bool | None = None,
) -> int:
    stmt = select(func.count(Portal.id))
    stmt = _apply_filters(stmt, is_supported=is_supported)
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_portal(session: AsyncSession, *, portal_id: str) -> Portal:
    result = await session.execute(select(Portal).where(Portal.id == portal_id))
    portal = result.scalar_one_or_none()
    if portal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "portal_not_found", "message": "Portal does not exist."},
        )
    return portal
