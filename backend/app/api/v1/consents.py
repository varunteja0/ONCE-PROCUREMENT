from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.schemas.consent import ConsentList, ConsentRead
from app.services import consent_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/consents", tags=["consents"])
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
            resource_type="consent",
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "consent_record_not_found",
            "message": "Consent record does not exist.",
        },
    )


@router.get("", response_model=ConsentList, summary="List consent records")
async def list_consents(
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    portal_id: Annotated[str | None, Query(max_length=36)] = None,
    active_only: Annotated[bool, Query()] = False,
    active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConsentList:
    # ``active`` is the canonical alias preferred by newer clients
    # (e.g. the browser extension). When both are supplied, ``active``
    # wins so the alias has stable precedence.
    effective_active_only = active if active is not None else active_only
    items, total = await consent_service.list_consents(
        session,
        tenant_id=tenant_user.tenant_id,
        supplier_id=supplier_id,
        portal_id=portal_id,
        active_only=effective_active_only,
        limit=limit,
        offset=offset,
    )
    _write_audit(
        session,
        action="consent.listed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=None,
        ip_address=_client_ip(request),
        metadata={
            "count": len(items),
            "total": total,
            "supplier_id": supplier_id,
            "portal_id": portal_id,
            "active_only": effective_active_only,
            "limit": limit,
            "offset": offset,
        },
    )
    _logger.info(
        "consents_listed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        count=len(items),
        total=total,
    )
    return ConsentList(
        items=[ConsentRead.model_validate(row) for row in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{consent_id}",
    response_model=ConsentRead,
    summary="Fetch a single consent record",
)
async def get_consent(
    consent_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConsentRead:
    try:
        row = await consent_service.get(session, tenant_id=tenant_user.tenant_id, consent_id=consent_id)
    except consent_service.NotFoundError as exc:
        raise _not_found() from exc
    _write_audit(
        session,
        action="consent.viewed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=row.id,
        ip_address=_client_ip(request),
        metadata={"supplier_id": row.supplier_id, "scope": row.scope.value},
    )
    return ConsentRead.model_validate(row)
