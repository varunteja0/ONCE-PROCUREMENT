from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, TenantUser
from app.schemas.tenant import TenantUpdate
from app.utils.logging import get_logger

__all__ = ["get_tenant", "update_tenant", "OWNER_ROLES"]


_logger = get_logger(__name__)

# Roles permitted to mutate tenant metadata.
OWNER_ROLES: frozenset[str] = frozenset({"owner", "admin"})


async def get_tenant(session: AsyncSession, tenant_id: str) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": "Tenant does not exist."},
        )
    return tenant


async def update_tenant(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor: TenantUser,
    payload: TenantUpdate,
) -> Tenant:
    if actor.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "cross_tenant_forbidden",
                "message": "Actor does not belong to the target tenant.",
            },
        )
    if actor.role not in OWNER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role",
                "message": "Only tenant owners may update tenant metadata.",
            },
        )

    tenant = await get_tenant(session, tenant_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return tenant

    for field, value in data.items():
        setattr(tenant, field, value)

    await session.flush()
    await session.refresh(tenant)
    _logger.info(
        "tenant_updated",
        tenant_id=tenant.id,
        actor_user_id=actor.user_id,
        fields=sorted(data.keys()),
    )
    return tenant
