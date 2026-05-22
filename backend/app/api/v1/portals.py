from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.portal import PortalList, PortalRead
from app.services import portal_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/portals", tags=["portals"])
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
            resource_type="portal",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


@router.get(
    "",
    response_model=PortalList,
    summary="List portals in the global catalog",
)
async def list_portals(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    is_supported: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PortalList:
    portals = await portal_service.list_portals(
        session, is_supported=is_supported, limit=limit, offset=offset
    )
    total = await portal_service.count_portals(session, is_supported=is_supported)
    response.headers["X-Total-Count"] = str(total)
    _write_audit(
        session,
        action="portal.listed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=None,
        ip_address=_client_ip(request),
        metadata={
            "count": len(portals),
            "is_supported": is_supported,
            "limit": limit,
            "offset": offset,
        },
    )
    return PortalList(
        items=[PortalRead.model_validate(p) for p in portals],
        total=total,
    )


@router.get(
    "/{portal_id}",
    response_model=PortalRead,
    summary="Fetch a single portal by id",
)
async def get_portal(
    portal_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalRead:
    portal = await portal_service.get_portal(session, portal_id=portal_id)
    _write_audit(
        session,
        action="portal.viewed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=portal.id,
        ip_address=_client_ip(request),
        metadata={"platform": portal.platform.value},
    )
    return PortalRead.model_validate(portal)
