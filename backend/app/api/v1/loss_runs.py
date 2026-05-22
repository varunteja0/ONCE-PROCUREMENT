"""REST API for the LossRun resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.loss_run import (
    LossRunCreate,
    LossRunList,
    LossRunRead,
    LossRunUpdate,
)
from app.services import loss_run_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/loss-runs", tags=["loss-runs"])
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
            resource_type="loss_run",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "loss_run_not_found", "message": "Loss run does not exist."},
    )


@router.post(
    "",
    response_model=LossRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a loss run",
)
async def create_loss_run(
    payload: LossRunCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LossRunRead:
    try:
        row = await loss_run_service.create(
            session, tenant_id=tenant_user.tenant_id, payload=payload
        )
    except loss_run_service.SupplierNotInTenantError as exc:
        # 404 (not 403) — never leak that the supplier exists in another tenant.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        ) from exc
    _audit(
        session,
        action="loss_run.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"supplier_id": row.supplier_id, "carrier_name": row.carrier_name},
    )
    return LossRunRead.model_validate(row)


@router.get("", response_model=LossRunList, summary="List loss runs")
async def list_loss_runs(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LossRunList:
    items, total = await loss_run_service.list_by_supplier(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return LossRunList(
        items=[LossRunRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{loss_run_id}", response_model=LossRunRead, summary="Fetch a loss run")
async def get_loss_run(
    loss_run_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LossRunRead:
    row = await loss_run_service.get(session, tenant_id=tenant_id, id=loss_run_id)
    if row is None:
        raise _not_found()
    return LossRunRead.model_validate(row)


@router.patch("/{loss_run_id}", response_model=LossRunRead, summary="Update a loss run")
async def update_loss_run(
    loss_run_id: str,
    payload: LossRunUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LossRunRead:
    try:
        row = await loss_run_service.update(
            session, tenant_id=tenant_user.tenant_id, id=loss_run_id, payload=payload
        )
    except loss_run_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="loss_run.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return LossRunRead.model_validate(row)


@router.delete(
    "/{loss_run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a loss run",
)
async def delete_loss_run(
    loss_run_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        row = await loss_run_service.delete(
            session, tenant_id=tenant_user.tenant_id, id=loss_run_id
        )
    except loss_run_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="loss_run.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"supplier_id": row.supplier_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
