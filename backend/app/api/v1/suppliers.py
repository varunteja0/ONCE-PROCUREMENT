from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.supplier import (
    SupplierCreate,
    SupplierListItem,
    SupplierRead,
    SupplierUpdate,
)
from app.services import supplier_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/suppliers", tags=["suppliers"])
_logger = get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _write_audit(
    session: AsyncSession,
    *,
    action: str,
    tenant_id: str,
    actor_user_id: str | None,
    resource_id: str | None,
    ip_address: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="supplier",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


@router.get(
    "",
    response_model=list[SupplierListItem],
    summary="List suppliers for the current tenant",
)
async def list_suppliers(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    search: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SupplierListItem]:
    suppliers = await supplier_service.list_suppliers(
        session,
        tenant_id=tenant_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    total = await supplier_service.count_suppliers(
        session, tenant_id=tenant_id, search=search
    )
    response.headers["X-Total-Count"] = str(total)
    return [SupplierListItem.model_validate(s) for s in suppliers]


@router.post(
    "",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a supplier",
)
async def create_supplier(
    payload: SupplierCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierRead:
    supplier = await supplier_service.create_supplier(
        session, tenant_id=tenant_user.tenant_id, payload=payload
    )
    _write_audit(
        session,
        action="supplier.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=supplier.id,
        ip_address=_client_ip(request),
        metadata={"legal_name": supplier.legal_name},
    )
    _logger.info(
        "supplier_created_api",
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier.id,
        actor_user_id=tenant_user.user_id,
    )
    return SupplierRead.model_validate(supplier)


@router.get(
    "/{supplier_id}",
    response_model=SupplierRead,
    summary="Fetch a single supplier",
)
async def get_supplier(
    supplier_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierRead:
    supplier = await supplier_service.get_supplier(
        session, tenant_id=tenant_id, supplier_id=supplier_id
    )
    return SupplierRead.model_validate(supplier)


@router.patch(
    "/{supplier_id}",
    response_model=SupplierRead,
    summary="Update a supplier",
)
async def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierRead:
    supplier = await supplier_service.update_supplier(
        session,
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier_id,
        payload=payload,
    )
    _write_audit(
        session,
        action="supplier.updated",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=supplier.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    _logger.info(
        "supplier_updated_api",
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier.id,
        actor_user_id=tenant_user.user_id,
    )
    return SupplierRead.model_validate(supplier)


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a supplier",
)
async def delete_supplier(
    supplier_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    supplier = await supplier_service.delete_supplier(
        session, tenant_id=tenant_user.tenant_id, supplier_id=supplier_id
    )
    _write_audit(
        session,
        action="supplier.deleted",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=supplier.id,
        ip_address=_client_ip(request),
        metadata={"legal_name": supplier.legal_name},
    )
    _logger.info(
        "supplier_deleted_api",
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier.id,
        actor_user_id=tenant_user.user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
