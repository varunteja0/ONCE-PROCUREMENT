"""REST API for the RiskSchedule resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.risk_schedule import (
    RiskScheduleCreate,
    RiskScheduleList,
    RiskScheduleRead,
    RiskScheduleUpdate,
)
from app.services import risk_schedule_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/risk-schedules", tags=["risk-schedules"])
_logger = get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _audit(
    session: AsyncSession,
    *,
    action: str,
    tenant_id: str,
    actor_user_id: str | None,
    resource_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="risk_schedule",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "risk_schedule_not_found",
            "message": "Risk schedule does not exist.",
        },
    )


@router.post(
    "",
    response_model=RiskScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a risk schedule",
)
async def create_risk_schedule(
    payload: RiskScheduleCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RiskScheduleRead:
    try:
        row = await risk_schedule_service.create(
            session, tenant_id=tenant_user.tenant_id, payload=payload
        )
    except risk_schedule_service.SupplierNotInTenantError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        ) from exc
    _audit(
        session,
        action="risk_schedule.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={
            "schedule_type": row.schedule_type,
            "item_count": row.item_count,
            "items_hash": row.items_hash,
        },
    )
    return RiskScheduleRead.model_validate(row)


@router.get("", response_model=RiskScheduleList, summary="List risk schedules")
async def list_risk_schedules(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RiskScheduleList:
    items, total = await risk_schedule_service.list_by_supplier(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return RiskScheduleList(
        items=[RiskScheduleRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{risk_schedule_id}",
    response_model=RiskScheduleRead,
    summary="Fetch a risk schedule",
)
async def get_risk_schedule(
    risk_schedule_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RiskScheduleRead:
    row = await risk_schedule_service.get(
        session, tenant_id=tenant_id, id=risk_schedule_id
    )
    if row is None:
        raise _not_found()
    return RiskScheduleRead.model_validate(row)


@router.patch(
    "/{risk_schedule_id}",
    response_model=RiskScheduleRead,
    summary="Update a risk schedule",
)
async def update_risk_schedule(
    risk_schedule_id: str,
    payload: RiskScheduleUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RiskScheduleRead:
    try:
        row = await risk_schedule_service.update(
            session,
            tenant_id=tenant_user.tenant_id,
            id=risk_schedule_id,
            payload=payload,
        )
    except risk_schedule_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="risk_schedule.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return RiskScheduleRead.model_validate(row)


@router.delete(
    "/{risk_schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a risk schedule",
)
async def delete_risk_schedule(
    risk_schedule_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        row = await risk_schedule_service.delete(
            session, tenant_id=tenant_user.tenant_id, id=risk_schedule_id
        )
    except risk_schedule_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="risk_schedule.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"schedule_type": row.schedule_type},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
