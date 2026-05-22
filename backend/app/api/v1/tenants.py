from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.tenant import TenantRead, TenantUpdate
from app.services import tenant_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/tenants", tags=["tenants"])
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
    resource_id: str,
    ip_address: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="tenant",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


@router.get(
    "/me",
    response_model=TenantRead,
    summary="Get the current authenticated tenant",
)
async def get_my_tenant(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantRead:
    tenant = await tenant_service.get_tenant(session, tenant_id)
    return TenantRead.model_validate(tenant)


@router.patch(
    "/me",
    response_model=TenantRead,
    summary="Update the current tenant (owner role required)",
)
async def update_my_tenant(
    payload: TenantUpdate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TenantRead:
    tenant = await tenant_service.update_tenant(
        session,
        tenant_id=tenant_user.tenant_id,
        actor=tenant_user,
        payload=payload,
    )
    _write_audit(
        session,
        action="tenant.updated",
        tenant_id=tenant.id,
        actor_user_id=tenant_user.user_id,
        resource_id=tenant.id,
        ip_address=_client_ip(request),
        metadata={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    _logger.info(
        "tenant_patched",
        tenant_id=tenant.id,
        actor_user_id=tenant_user.user_id,
    )
    return TenantRead.model_validate(tenant)
