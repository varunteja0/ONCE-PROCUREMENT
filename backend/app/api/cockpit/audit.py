"""Read-only cockpit audit log."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cockpit import CurrentOperator
from app.db import get_db
from app.models import CockpitAudit
from app.schemas.cockpit import CockpitAuditListResponse, CockpitAuditRead

__all__ = ["router"]

router = APIRouter(prefix="/audit", tags=["cockpit-audit"])


@router.get(
    "",
    response_model=CockpitAuditListResponse,
    summary="Recent cockpit audit entries",
)
async def list_audit(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    operator_id: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
) -> CockpitAuditListResponse:
    stmt = select(CockpitAudit)
    count_stmt = select(func.count(CockpitAudit.id))
    if operator_id:
        stmt = stmt.where(CockpitAudit.operator_id == operator_id)
        count_stmt = count_stmt.where(CockpitAudit.operator_id == operator_id)
    if tenant_id:
        stmt = stmt.where(CockpitAudit.tenant_id_acted_as == tenant_id)
        count_stmt = count_stmt.where(CockpitAudit.tenant_id_acted_as == tenant_id)

    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    result = await session.execute(
        stmt.order_by(CockpitAudit.occurred_at.desc()).offset(offset).limit(limit)
    )
    rows = list(result.scalars().all())
    return CockpitAuditListResponse(
        items=[CockpitAuditRead.model_validate(r) for r in rows],
        total=total,
    )
