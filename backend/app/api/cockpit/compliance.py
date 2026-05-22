"""SOC 2 evidence read endpoints + key rotation ledger.

All routes here live under ``/cockpit/compliance`` and require a
cockpit-authenticated operator. Write paths (key rotation log entries,
tenant deletion) additionally require the ``FOUNDER`` role via
:func:`require_founder`.

Responsibilities:

* ``GET /audit-export`` — stream a tenant's ``audit_logs`` for a window,
  in JSON Lines (default) or CSV. Founder-only.
* ``GET /access-review`` — list every (tenant, user) membership for one
  tenant. Founder-only.
* ``GET /audit-hash-digests`` — list stored daily digests for one tenant,
  so an auditor can re-verify the chain externally.
* ``POST /key-rotations`` — append-only ledger entry. Founder-only.
* ``GET /key-rotations`` — list rotation ledger entries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cockpit import CurrentOperator, FounderOperator
from app.db import get_db
from app.models import AuditHashDigest, Tenant
from app.schemas.compliance import (
    AccessReviewResponse,
    AuditHashDigestListResponse,
    AuditHashDigestRead,
    KeyRotationCreate,
    KeyRotationListResponse,
    KeyRotationRead,
)
from app.services import (
    access_review_service,
    audit_export_service,
    key_rotation_service,
)
from app.services.exceptions import OnceError
from app.utils.logging import get_logger

__all__ = ["router"]

router = APIRouter(prefix="/compliance", tags=["cockpit-compliance"])
_logger = get_logger(__name__)


_MAX_EXPORT_WINDOW_DAYS = 366  # one calendar year, hard cap


async def _ensure_tenant_exists(session: AsyncSession, tenant_id: str) -> Tenant:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tenant_not_found", "message": "Tenant does not exist."},
        )
    return tenant


def _validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_window",
                "message": "`end` must be strictly greater than `start`.",
            },
        )
    if (end - start).days > _MAX_EXPORT_WINDOW_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "window_too_large",
                "message": (
                    f"Export window cannot exceed {_MAX_EXPORT_WINDOW_DAYS} days."
                ),
            },
        )
    return start, end


# ---------------------------------------------------------------------------
# Audit export
# ---------------------------------------------------------------------------


@router.get(
    "/audit-export",
    summary="Export a tenant's audit log for a time window (JSONL or CSV)",
)
async def export_audit_logs(
    operator: FounderOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: str = Query(..., min_length=1, max_length=36),
    start: datetime = Query(...),
    end: datetime = Query(...),
    format: Literal["jsonl", "csv"] = Query(default="jsonl"),
) -> Response:
    start, end = _validate_window(start, end)
    await _ensure_tenant_exists(session, tenant_id)

    if format == "csv":
        body = await audit_export_service.to_csv_bytes(
            session, tenant_id=tenant_id, start=start, end=end
        )
        media_type = "text/csv"
        filename = f"audit-{tenant_id}-{start.date()}-{end.date()}.csv"
    else:
        body = await audit_export_service.to_jsonl_bytes(
            session, tenant_id=tenant_id, start=start, end=end
        )
        media_type = "application/x-ndjson"
        filename = f"audit-{tenant_id}-{start.date()}-{end.date()}.jsonl"

    _logger.info(
        "compliance_audit_exported",
        operator_id=operator.id,
        tenant_id=tenant_id,
        start=start.isoformat(),
        end=end.isoformat(),
        format=format,
        bytes=len(body),
    )

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Access review
# ---------------------------------------------------------------------------


@router.get(
    "/access-review",
    response_model=AccessReviewResponse,
    summary="List every user with access to a tenant",
)
async def access_review(
    operator: FounderOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: str = Query(..., min_length=1, max_length=36),
) -> AccessReviewResponse:
    await _ensure_tenant_exists(session, tenant_id)
    result = await access_review_service.list_tenant_users(
        session, tenant_id=tenant_id
    )
    _logger.info(
        "compliance_access_reviewed",
        operator_id=operator.id,
        tenant_id=tenant_id,
        total=result.total,
    )
    return result


# ---------------------------------------------------------------------------
# Audit hash digests
# ---------------------------------------------------------------------------


@router.get(
    "/audit-hash-digests",
    response_model=AuditHashDigestListResponse,
    summary="List nightly audit-hash digests for a tenant (chain inspection)",
)
async def list_audit_hash_digests(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: str = Query(..., min_length=1, max_length=36),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditHashDigestListResponse:
    await _ensure_tenant_exists(session, tenant_id)
    count_stmt = (
        select(func.count(AuditHashDigest.id))
        .where(AuditHashDigest.tenant_id == tenant_id)
    )
    total = int((await session.execute(count_stmt)).scalar_one() or 0)
    rows = list(
        (
            await session.execute(
                select(AuditHashDigest)
                .where(AuditHashDigest.tenant_id == tenant_id)
                .order_by(AuditHashDigest.covers_date.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    _logger.info(
        "compliance_audit_hash_listed",
        operator_id=operator.id,
        tenant_id=tenant_id,
        total=total,
    )
    return AuditHashDigestListResponse(
        tenant_id=tenant_id,
        total=total,
        items=[AuditHashDigestRead.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Key rotation log
# ---------------------------------------------------------------------------


@router.post(
    "/key-rotations",
    response_model=KeyRotationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a key/secret rotation event (append-only ledger)",
)
async def record_key_rotation(
    payload: KeyRotationCreate,
    operator: FounderOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> KeyRotationRead:
    try:
        row = await key_rotation_service.record_rotation(
            session, payload=payload, operator_id=operator.id
        )
    except OnceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": exc.message,
                "message": "Rejected: " + exc.message,
                "context": exc.context,
            },
        ) from exc
    await session.commit()
    return KeyRotationRead.model_validate(row)


@router.get(
    "/key-rotations",
    response_model=KeyRotationListResponse,
    summary="List recorded key/secret rotations",
)
async def list_key_rotations(
    operator: CurrentOperator,
    session: Annotated[AsyncSession, Depends(get_db)],
    key_name: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> KeyRotationListResponse:
    _ = operator  # auth gate only
    return await key_rotation_service.list_rotations(
        session, key_name=key_name, limit=limit, offset=offset
    )
