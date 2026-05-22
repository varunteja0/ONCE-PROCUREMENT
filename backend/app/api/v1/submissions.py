from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.db import get_db
from app.models import AuditLog
from app.models.submission import SubmissionStatus
from app.schemas.receipt import ReceiptRead
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionListItem,
    SubmissionRead,
)
from app.services import submission_service
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/submissions", tags=["submissions"])
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
    resource_type: str,
    ip_address: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def _verify_url(request: Request, receipt_id: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/verify/{receipt_id}"


@router.post(
    "",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Queue a new submission to a portal",
)
async def create_submission(
    payload: SubmissionCreate,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionRead:
    submission = await submission_service.create_submission(
        session, tenant_id=tenant_user.tenant_id, payload=payload
    )
    _write_audit(
        session,
        action="submission.created",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=submission.id,
        resource_type="submission",
        ip_address=_client_ip(request),
        metadata={
            "supplier_id": submission.supplier_id,
            "portal_id": submission.portal_id,
            "consent_record_id": submission.consent_record_id,
        },
    )
    _logger.info(
        "submission_created_api",
        tenant_id=tenant_user.tenant_id,
        submission_id=submission.id,
        actor_user_id=tenant_user.user_id,
    )
    return SubmissionRead.model_validate(submission)


@router.get(
    "",
    response_model=list[SubmissionListItem],
    summary="List submissions for the current tenant",
)
async def list_submissions(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    status_filter: Annotated[SubmissionStatus | None, Query(alias="status")] = None,
    supplier_id: Annotated[str | None, Query(max_length=36)] = None,
    portal_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SubmissionListItem]:
    submissions = await submission_service.list_submissions(
        session,
        tenant_id=tenant_id,
        status_filter=status_filter,
        supplier_id=supplier_id,
        portal_id=portal_id,
        limit=limit,
        offset=offset,
    )
    total = await submission_service.count_submissions(
        session,
        tenant_id=tenant_id,
        status_filter=status_filter,
        supplier_id=supplier_id,
        portal_id=portal_id,
    )
    response.headers["X-Total-Count"] = str(total)
    return [SubmissionListItem.model_validate(s) for s in submissions]


@router.get(
    "/{submission_id}",
    response_model=SubmissionRead,
    summary="Fetch a single submission",
)
async def get_submission(
    submission_id: str,
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionRead:
    submission = await submission_service.get_submission(
        session, tenant_id=tenant_id, submission_id=submission_id
    )
    return SubmissionRead.model_validate(submission)


@router.post(
    "/{submission_id}/retry",
    response_model=SubmissionRead,
    summary="Re-queue a failed or blocked submission",
)
async def retry_submission(
    submission_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubmissionRead:
    submission = await submission_service.retry_submission(
        session, tenant_id=tenant_user.tenant_id, submission_id=submission_id
    )
    _write_audit(
        session,
        action="submission.retried",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=submission.id,
        resource_type="submission",
        ip_address=_client_ip(request),
        metadata={"attempt_count": submission.attempt_count},
    )
    _logger.info(
        "submission_retried_api",
        tenant_id=tenant_user.tenant_id,
        submission_id=submission.id,
        actor_user_id=tenant_user.user_id,
    )
    return SubmissionRead.model_validate(submission)


@router.get(
    "/{submission_id}/receipt",
    response_model=ReceiptRead,
    summary="Fetch the signed receipt for a submission",
)
async def get_submission_receipt(
    submission_id: str,
    request: Request,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReceiptRead:
    receipt = await submission_service.get_receipt_for_submission(
        session, tenant_id=tenant_user.tenant_id, submission_id=submission_id
    )
    _write_audit(
        session,
        action="receipt.viewed",
        tenant_id=tenant_user.tenant_id,
        actor_user_id=tenant_user.user_id,
        resource_id=receipt.id,
        resource_type="receipt",
        ip_address=_client_ip(request),
        metadata={"submission_id": submission_id},
    )
    data = ReceiptRead.model_validate(receipt).model_copy(
        update={"verify_url": _verify_url(request, receipt.id)}
    )
    return data
