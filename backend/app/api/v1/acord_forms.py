"""REST API for the AcordForm resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.acord_form import (
    AcordFormCreate,
    AcordFormList,
    AcordFormRead,
    AcordFormUpdate,
)
from app.services import acord_form_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/acord-forms", tags=["acord-forms"])
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
            resource_type="acord_form",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "acord_form_not_found",
            "message": "ACORD form does not exist.",
        },
    )


@router.post(
    "",
    response_model=AcordFormRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an ACORD form",
)
async def create_acord_form(
    payload: AcordFormCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AcordFormRead:
    try:
        row = await acord_form_service.create(
            session, tenant_id=tenant_user.tenant_id, payload=payload
        )
    except acord_form_service.SupplierNotInTenantError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        ) from exc
    except acord_form_service.InvalidSupersedeReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_supersede_reference",
                "message": "superseded_by_id does not reference a valid ACORD form.",
            },
        ) from exc
    _audit(
        session,
        action="acord_form.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"form_type": row.form_type, "payload_hash": row.payload_hash},
    )
    return AcordFormRead.model_validate(row)


@router.get("", response_model=AcordFormList, summary="List ACORD forms")
async def list_acord_forms(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AcordFormList:
    items, total = await acord_form_service.list_by_supplier(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return AcordFormList(
        items=[AcordFormRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{acord_form_id}",
    response_model=AcordFormRead,
    summary="Fetch an ACORD form",
)
async def get_acord_form(
    acord_form_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AcordFormRead:
    row = await acord_form_service.get(
        session, tenant_id=tenant_id, id=acord_form_id
    )
    if row is None:
        raise _not_found()
    return AcordFormRead.model_validate(row)


@router.patch(
    "/{acord_form_id}",
    response_model=AcordFormRead,
    summary="Update an ACORD form",
)
async def update_acord_form(
    acord_form_id: str,
    payload: AcordFormUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AcordFormRead:
    try:
        row = await acord_form_service.update(
            session,
            tenant_id=tenant_user.tenant_id,
            id=acord_form_id,
            payload=payload,
        )
    except acord_form_service.NotFoundError as exc:
        raise _not_found() from exc
    except acord_form_service.InvalidSupersedeReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_supersede_reference",
                "message": "superseded_by_id does not reference a valid ACORD form.",
            },
        ) from exc
    _audit(
        session,
        action="acord_form.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return AcordFormRead.model_validate(row)


@router.delete(
    "/{acord_form_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an ACORD form",
)
async def delete_acord_form(
    acord_form_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        row = await acord_form_service.delete(
            session, tenant_id=tenant_user.tenant_id, id=acord_form_id
        )
    except acord_form_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="acord_form.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"form_type": row.form_type},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
