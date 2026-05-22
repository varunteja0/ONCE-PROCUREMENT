"""L3.10 — Tenant audit-trail API.

Endpoints (all tenant-scoped; cross-tenant reads are filtered server-side):

* ``GET    /v1/audit``                                            list + filter
* ``GET    /v1/audit/{id}``                                       single row
* ``GET    /v1/audit/chain/verify``                               chain replay
* ``GET    /v1/audit/by-resource/{resource_type}/{resource_id}``  resource history
* ``POST   /v1/audit/exports``                                    queue export
* ``GET    /v1/audit/exports``                                    list exports
* ``GET    /v1/audit/exports/{id}``                               export status
* ``GET    /v1/audit/exports/{id}/download``                      PDF bytes
* ``GET    /v1/audit/exports/{id}/download/envelope``             JSON envelope
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentUser
from app.db import get_db
from app.models.audit_export import (
    AuditExport,
    AuditExportStatus,
)
from app.models.audit_log import AuditActorType, AuditLogEntry
from app.schemas.audit import (
    AuditChainVerifyResult,
    AuditExportCreate,
    AuditExportListItem,
    AuditExportRead,
    AuditLogList,
    AuditLogRead,
)
from app.services.audit_chain import verify_chain
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/audit", tags=["audit"])
_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Accept trailing Z; fromisoformat doesn't.
        normalised = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_datetime", "message": str(exc)},
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def _get_export_or_404(
    session: AsyncSession, *, tenant_id: str, export_id: str
) -> AuditExport:
    row = await session.get(AuditExport, export_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Export not found."},
        )
    return row


# ---------------------------------------------------------------------------
# List / filter / search
# ---------------------------------------------------------------------------


@router.get("", response_model=AuditLogList)
async def list_audit_rows(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    actor_type: AuditActorType | None = Query(default=None),
    action: str | None = Query(default=None, max_length=64),
    resource_type: str | None = Query(default=None, max_length=64),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditLogList:
    stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == tenant_id)
    count_stmt = select(AuditLogEntry.id).where(AuditLogEntry.tenant_id == tenant_id)

    filters: list = []
    if actor_type:
        filters.append(AuditLogEntry.actor_type == actor_type)
    if action:
        filters.append(AuditLogEntry.action_verb == action)
    if resource_type:
        filters.append(AuditLogEntry.resource_type == resource_type)
    start = _parse_dt(from_)
    end = _parse_dt(to)
    if start is not None:
        filters.append(AuditLogEntry.occurred_at >= start)
    if end is not None:
        filters.append(AuditLogEntry.occurred_at < end)
    if q:
        like = f"%{q.lower()}%"
        filters.append(
            or_(
                AuditLogEntry.resource_label.ilike(like),
                AuditLogEntry.resource_id.ilike(like),
                AuditLogEntry.action_verb.ilike(like),
            )
        )
    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    stmt = (
        stmt.order_by(AuditLogEntry.occurred_at.desc(), AuditLogEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    total = len(list((await session.execute(count_stmt)).scalars().all()))

    return AuditLogList(
        items=[AuditLogRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Chain verification — declared BEFORE `/{id}` so it doesn't get matched
# as `id == "chain"`.
# ---------------------------------------------------------------------------


@router.get("/chain/verify", response_model=AuditChainVerifyResult)
async def chain_verify(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_position: int = Query(default=1, ge=1),
    to_position: int | None = Query(default=None, ge=1),
) -> AuditChainVerifyResult:
    return await verify_chain(
        session,
        tenant_id=tenant_id,
        from_position=from_position,
        to_position=to_position,
    )


# ---------------------------------------------------------------------------
# Per-resource history
# ---------------------------------------------------------------------------


@router.get(
    "/by-resource/{resource_type}/{resource_id}",
    response_model=AuditLogList,
)
async def by_resource(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    resource_type: str,
    resource_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
) -> AuditLogList:
    stmt = (
        select(AuditLogEntry)
        .where(AuditLogEntry.tenant_id == tenant_id)
        .where(AuditLogEntry.resource_type == resource_type)
        .where(AuditLogEntry.resource_id == resource_id)
        .order_by(AuditLogEntry.occurred_at.asc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return AuditLogList(
        items=[AuditLogRead.model_validate(r) for r in rows],
        total=len(rows),
        limit=limit,
        offset=0,
    )


# ---------------------------------------------------------------------------
# Exports — list / create / status / download
# ---------------------------------------------------------------------------


@router.get("/exports", response_model=list[AuditExportListItem])
async def list_exports(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditExportListItem]:
    stmt = (
        select(AuditExport)
        .where(AuditExport.tenant_id == tenant_id)
        .order_by(AuditExport.requested_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [AuditExportListItem.model_validate(r) for r in rows]


@router.post(
    "/exports",
    response_model=AuditExportRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    tenant_id: CurrentTenantId,
    user: CurrentUser,
    body: AuditExportCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditExportRead:
    # Rate-limit: at most one active export per tenant.
    active_stmt = (
        select(AuditExport.id)
        .where(AuditExport.tenant_id == tenant_id)
        .where(
            AuditExport.status.in_(
                [AuditExportStatus.PENDING, AuditExportStatus.GENERATING]
            )
        )
        .limit(1)
    )
    if (await session.execute(active_stmt)).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "export_in_progress",
                "message": "Another export is already running for this tenant.",
            },
        )

    export = AuditExport(
        tenant_id=tenant_id,
        scope_type=body.scope,
        scope_params=body.scope_params,
        requested_by_user_id=str(user.id),
        status=AuditExportStatus.PENDING,
    )
    session.add(export)
    await session.flush()

    # Best-effort enqueue. If Celery isn't configured (tests / local dev),
    # the worker layer surfaces the export through the synchronous
    # generate_audit_export_sync helper exposed below. We use
    # ``apply_async(retry=False)`` so a broker that's unreachable raises
    # immediately rather than blocking the request for the connection
    # retry backoff window.
    try:
        from app.workers.tasks.audit_tasks import generate_audit_export_task

        generate_audit_export_task.apply_async(
            args=(export.id,), retry=False
        )
    except Exception as exc:  # noqa: BLE001
        _logger.warning(
            "audit_export_enqueue_failed",
            export_id=export.id,
            error_type=type(exc).__name__,
            error=str(exc),
        )

    return AuditExportRead.model_validate(export)


@router.get("/exports/{export_id}", response_model=AuditExportRead)
async def get_export(
    tenant_id: CurrentTenantId,
    export_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditExportRead:
    row = await _get_export_or_404(session, tenant_id=tenant_id, export_id=export_id)
    return AuditExportRead.model_validate(row)


@router.get("/exports/{export_id}/download")
async def download_export_pdf(
    tenant_id: CurrentTenantId,
    export_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    row = await _get_export_or_404(session, tenant_id=tenant_id, export_id=export_id)
    if row.status != AuditExportStatus.READY or not row.file_path:
        raise HTTPException(
            status_code=409,
            detail={"code": "not_ready", "message": f"Export is {row.status.value}."},
        )
    if not os.path.exists(row.file_path):
        raise HTTPException(
            status_code=410,
            detail={"code": "expired", "message": "Export file has expired."},
        )
    return FileResponse(
        row.file_path,
        media_type="application/pdf",
        filename=f"once-audit-{export_id}.pdf",
    )


@router.get("/exports/{export_id}/download/envelope")
async def download_export_envelope(
    tenant_id: CurrentTenantId,
    export_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    row = await _get_export_or_404(session, tenant_id=tenant_id, export_id=export_id)
    if row.status != AuditExportStatus.READY or not row.signed_envelope_path:
        raise HTTPException(
            status_code=409,
            detail={"code": "not_ready", "message": f"Export is {row.status.value}."},
        )
    if not os.path.exists(row.signed_envelope_path):
        raise HTTPException(
            status_code=410,
            detail={"code": "expired", "message": "Envelope file has expired."},
        )
    with open(row.signed_envelope_path, "rb") as fh:
        body = fh.read()
    # Validate JSON before returning so an on-disk corruption surfaces as 5xx.
    json.loads(body.decode("utf-8"))
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="once-audit-{export_id}.envelope.json"'
            )
        },
    )


# ---------------------------------------------------------------------------
# Single-row detail (declared LAST so the literal segments above match first).
# ---------------------------------------------------------------------------


@router.get("/{audit_id}", response_model=AuditLogRead)
async def get_audit_row(
    tenant_id: CurrentTenantId,
    audit_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditLogRead:
    row = await session.get(AuditLogEntry, audit_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Audit row not found."},
        )
    return AuditLogRead.model_validate(row)
