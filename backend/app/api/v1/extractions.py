"""L3.8 - REST API for PDF metadata extraction."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.models.extraction_result import ExtractionSourceType
from app.schemas.extractions import (
    ExtractionAcceptRequest,
    ExtractionEnqueueRequest,
    ExtractionList,
    ExtractionRead,
    ExtractionRejectRequest,
)
from app.services import extraction_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/extractions", tags=["extractions"])
_logger = get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    if request.client is not None and request.client.host:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return None


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "extraction_not_found",
            "message": "Extraction does not exist.",
        },
    )


@router.post(
    "/document",
    response_model=ExtractionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a PDF extraction",
)
async def enqueue_extraction(
    payload: ExtractionEnqueueRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionRead:
    row = await extraction_service.create_extraction_record(
        session,
        tenant_id=tenant_user.tenant_id,
        document_type=payload.document_type,
        document_id=payload.document_id,
    )
    # Best-effort enqueue. We import locally to avoid pulling Celery into the
    # FastAPI startup path for tests / environments where Redis isn't available.
    try:
        from app.workers.tasks.extraction_tasks import extract_document
        extract_document.delay(row.id)
    except Exception as exc:
        _logger.warning(
            "extraction_enqueue_failed",
            extraction_id=row.id,
            error=str(exc),
        )
    session.add(
        AuditLog(
            tenant_id=tenant_user.tenant_id,
            actor_user_id=tenant_user.user_id,
            action="extraction.enqueued",
            resource_type="extraction_result",
            resource_id=row.id,
            metadata_json={
                "document_type": row.source_document_type,
                "document_id": row.source_document_id,
            },
            ip_address=_client_ip(request),
        )
    )
    await session.commit()
    await session.refresh(row)
    return ExtractionRead.model_validate(row)


@router.get(
    "/{extraction_id}",
    response_model=ExtractionRead,
    summary="Fetch an extraction",
)
async def get_extraction(
    extraction_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionRead:
    row = await extraction_service.get_extraction(
        session, tenant_id=tenant_id, extraction_id=extraction_id
    )
    if row is None:
        raise _not_found()
    return ExtractionRead.model_validate(row)


@router.get(
    "",
    response_model=ExtractionList,
    summary="List extractions",
)
async def list_extractions(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    document_type: Annotated[ExtractionSourceType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExtractionList:
    items, total = await extraction_service.list_extractions(
        session,
        tenant_id=tenant_id,
        document_type=document_type,
        limit=limit,
        offset=offset,
    )
    return ExtractionList(
        items=[ExtractionRead.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{extraction_id}/accept",
    response_model=ExtractionRead,
    summary="Accept an extraction with optional field overrides",
)
async def accept_extraction(
    extraction_id: str,
    payload: ExtractionAcceptRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionRead:
    try:
        row = await extraction_service.accept_extraction(
            session,
            tenant_id=tenant_user.tenant_id,
            extraction_id=extraction_id,
            user_id=tenant_user.user_id,
            fields=payload.fields,
        )
    except extraction_service.ExtractionNotFoundError as exc:
        raise _not_found() from exc
    session.add(
        AuditLog(
            tenant_id=tenant_user.tenant_id,
            actor_user_id=tenant_user.user_id,
            action="extraction.accepted",
            resource_type="extraction_result",
            resource_id=row.id,
            metadata_json={"overrides": sorted(payload.fields.keys())},
            ip_address=_client_ip(request),
        )
    )
    await session.commit()
    await session.refresh(row)
    return ExtractionRead.model_validate(row)


@router.post(
    "/{extraction_id}/reject",
    response_model=ExtractionRead,
    summary="Reject an extraction (flag for future model improvement)",
)
async def reject_extraction(
    extraction_id: str,
    payload: ExtractionRejectRequest,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionRead:
    try:
        row = await extraction_service.reject_extraction(
            session,
            tenant_id=tenant_user.tenant_id,
            extraction_id=extraction_id,
            user_id=tenant_user.user_id,
            reason=payload.reason,
        )
    except extraction_service.ExtractionNotFoundError as exc:
        raise _not_found() from exc
    session.add(
        AuditLog(
            tenant_id=tenant_user.tenant_id,
            actor_user_id=tenant_user.user_id,
            action="extraction.rejected",
            resource_type="extraction_result",
            resource_id=row.id,
            metadata_json={"reason": payload.reason},
            ip_address=_client_ip(request),
        )
    )
    await session.commit()
    await session.refresh(row)
    return ExtractionRead.model_validate(row)
