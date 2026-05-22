"""REST API for the EOCertificate resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.eo_certificate import (
    EOCertificateCreate,
    EOCertificateList,
    EOCertificateRead,
    EOCertificateUpdate,
)
from app.services import eo_certificate_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/eo-certificates", tags=["eo-certificates"])
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
            resource_type="eo_certificate",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "eo_certificate_not_found",
            "message": "E&O certificate does not exist.",
        },
    )


@router.post(
    "",
    response_model=EOCertificateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an E&O certificate",
)
async def create_eo_certificate(
    payload: EOCertificateCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EOCertificateRead:
    try:
        row = await eo_certificate_service.create(
            session, tenant_id=tenant_user.tenant_id, payload=payload
        )
    except eo_certificate_service.SupplierNotInTenantError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        ) from exc
    _audit(
        session,
        action="eo_certificate.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"policy_number": row.policy_number, "carrier_name": row.carrier_name},
    )
    return EOCertificateRead.model_validate(row)


@router.get(
    "", response_model=EOCertificateList, summary="List E&O certificates"
)
async def list_eo_certificates(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EOCertificateList:
    items, total = await eo_certificate_service.list_by_supplier(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return EOCertificateList(
        items=[EOCertificateRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{eo_certificate_id}",
    response_model=EOCertificateRead,
    summary="Fetch an E&O certificate",
)
async def get_eo_certificate(
    eo_certificate_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EOCertificateRead:
    row = await eo_certificate_service.get(
        session, tenant_id=tenant_id, id=eo_certificate_id
    )
    if row is None:
        raise _not_found()
    return EOCertificateRead.model_validate(row)


@router.patch(
    "/{eo_certificate_id}",
    response_model=EOCertificateRead,
    summary="Update an E&O certificate",
)
async def update_eo_certificate(
    eo_certificate_id: str,
    payload: EOCertificateUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EOCertificateRead:
    try:
        row = await eo_certificate_service.update(
            session,
            tenant_id=tenant_user.tenant_id,
            id=eo_certificate_id,
            payload=payload,
        )
    except eo_certificate_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="eo_certificate.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return EOCertificateRead.model_validate(row)


@router.delete(
    "/{eo_certificate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an E&O certificate",
)
async def delete_eo_certificate(
    eo_certificate_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        row = await eo_certificate_service.delete(
            session, tenant_id=tenant_user.tenant_id, id=eo_certificate_id
        )
    except eo_certificate_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="eo_certificate.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"policy_number": row.policy_number},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
