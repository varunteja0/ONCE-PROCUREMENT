"""REST API for the ProducerLicense resource."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.producer_license import (
    ProducerLicenseCreate,
    ProducerLicenseList,
    ProducerLicenseRead,
    ProducerLicenseUpdate,
)
from app.services import producer_license_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/producer-licenses", tags=["producer-licenses"])
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
            resource_type="producer_license",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "producer_license_not_found",
            "message": "Producer license does not exist.",
        },
    )


@router.post(
    "",
    response_model=ProducerLicenseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a producer license",
)
async def create_producer_license(
    payload: ProducerLicenseCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProducerLicenseRead:
    try:
        row = await producer_license_service.create(
            session, tenant_id=tenant_user.tenant_id, payload=payload
        )
    except producer_license_service.SupplierNotInTenantError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "supplier_not_found", "message": "Supplier does not exist."},
        ) from exc
    except producer_license_service.DuplicateLicenseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "license_already_exists",
                "message": "A license already exists for this supplier/state/number.",
            },
        ) from exc
    _audit(
        session,
        action="producer_license.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"state": row.state, "license_number": row.license_number},
    )
    return ProducerLicenseRead.model_validate(row)


@router.get(
    "", response_model=ProducerLicenseList, summary="List producer licenses"
)
async def list_producer_licenses(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProducerLicenseList:
    items, total = await producer_license_service.list_by_supplier(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return ProducerLicenseList(
        items=[ProducerLicenseRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{license_id}",
    response_model=ProducerLicenseRead,
    summary="Fetch a producer license",
)
async def get_producer_license(
    license_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProducerLicenseRead:
    row = await producer_license_service.get(
        session, tenant_id=tenant_id, id=license_id
    )
    if row is None:
        raise _not_found()
    return ProducerLicenseRead.model_validate(row)


@router.patch(
    "/{license_id}",
    response_model=ProducerLicenseRead,
    summary="Update a producer license",
)
async def update_producer_license(
    license_id: str,
    payload: ProducerLicenseUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProducerLicenseRead:
    try:
        row = await producer_license_service.update(
            session,
            tenant_id=tenant_user.tenant_id,
            id=license_id,
            payload=payload,
        )
    except producer_license_service.NotFoundError as exc:
        raise _not_found() from exc
    except producer_license_service.DuplicateLicenseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "license_already_exists",
                "message": "A license already exists for this supplier/state/number.",
            },
        ) from exc
    _audit(
        session,
        action="producer_license.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return ProducerLicenseRead.model_validate(row)


@router.delete(
    "/{license_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a producer license",
)
async def delete_producer_license(
    license_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        row = await producer_license_service.delete(
            session, tenant_id=tenant_user.tenant_id, id=license_id
        )
    except producer_license_service.NotFoundError as exc:
        raise _not_found() from exc
    _audit(
        session,
        action="producer_license.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"state": row.state, "license_number": row.license_number},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
