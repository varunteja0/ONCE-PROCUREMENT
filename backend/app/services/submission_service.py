from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    ConsentRecord,
    Portal,
    PortalPlatform,
    SubmissionReceipt,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
)
from app.models.consent import ConsentScope
from app.schemas.submission import SubmissionCreate
from app.utils.logging import get_logger

__all__ = [
    "create_submission",
    "list_submissions",
    "count_submissions",
    "get_submission",
    "retry_submission",
    "get_receipt_for_submission",
]


_logger = get_logger(__name__)

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

_RETRYABLE_STATUSES: frozenset[SubmissionStatus] = frozenset({SubmissionStatus.FAILED, SubmissionStatus.BLOCKED})
_WRITE_CONSENT_SCOPES: frozenset[ConsentScope] = frozenset(
    {ConsentScope.SUBMIT_ON_BEHALF, ConsentScope.SUBMIT_AND_SIGN}
)


def _clamp_limit(limit: int) -> int:
    if limit <= 0:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _enqueue(submission_id: str, session: AsyncSession) -> None:
    """Dispatch the submission either inline (tests) or via Celery (prod).

    Imports are performed lazily so ``submission_service`` stays import-safe
    in unit-test contexts where Celery / Redis are unavailable.
    """

    if settings.enable_in_process_processor:
        try:
            from app.services.submission_pipeline import process_submission
        except Exception:  # pragma: no cover - defensive: pipeline optional in tests
            _logger.warning(
                "submission_inline_pipeline_unavailable",
                submission_id=submission_id,
            )
            return
        try:
            await process_submission(submission_id, session)
        except Exception:
            _logger.exception(
                "submission_inline_dispatch_failed",
                submission_id=submission_id,
            )
        return

    try:
        from app.workers.tasks.submission_tasks import process_submission_task
    except Exception:  # pragma: no cover - celery layer not present in tests
        _logger.warning(
            "submission_celery_unavailable_skipping_dispatch",
            submission_id=submission_id,
        )
        return

    try:
        process_submission_task.delay(submission_id)
    except Exception:
        _logger.exception(
            "submission_celery_dispatch_failed",
            submission_id=submission_id,
        )


async def _load_supplier(session: AsyncSession, *, tenant_id: str, supplier_id: str) -> Supplier:
    stmt = select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
    result = await session.execute(stmt)
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "supplier_not_found",
                "message": "Supplier does not exist for this tenant.",
            },
        )
    return supplier


async def _load_portal(session: AsyncSession, *, portal_id: str) -> Portal:
    result = await session.execute(select(Portal).where(Portal.id == portal_id))
    portal = result.scalar_one_or_none()
    if portal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "portal_not_found", "message": "Portal does not exist."},
        )
    return portal


async def _load_consent(
    session: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
    consent_record_id: str,
) -> ConsentRecord:
    stmt = select(ConsentRecord).where(
        ConsentRecord.id == consent_record_id,
        ConsentRecord.tenant_id == tenant_id,
        ConsentRecord.supplier_id == supplier_id,
    )
    result = await session.execute(stmt)
    consent = result.scalar_one_or_none()
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "consent_record_not_found",
                "message": "Consent record does not exist for this supplier.",
            },
        )
    return consent


def _validate_portal_supported(portal: Portal) -> None:
    if not portal.is_supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "portal_unsupported",
                "message": f"Portal '{portal.display_name}' is not currently supported.",
            },
        )
    if portal.risky and not settings.enable_tos_risky_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "portal_risky_disabled",
                "message": (
                    f"Portal '{portal.display_name}' is flagged risky and disabled "
                    "by the ENABLE_TOS_RISKY_PLATFORMS feature gate."
                ),
            },
        )


def _validate_consent_covers_portal(consent: ConsentRecord, portal: Portal) -> None:
    if consent.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "consent_revoked",
                "message": "Consent record has been revoked.",
            },
        )
    if consent.scope not in _WRITE_CONSENT_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "consent_scope_insufficient",
                "message": ("Consent scope does not authorize submitting on behalf of the supplier."),
            },
        )

    portal_ids = consent.portal_ids_json or []
    if portal_ids and "*" not in portal_ids and portal.id not in portal_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "consent_portal_not_covered",
                "message": "Consent record does not cover the requested portal.",
            },
        )


async def create_submission(
    session: AsyncSession,
    *,
    tenant_id: str,
    payload: SubmissionCreate,
) -> SupplierSubmission:
    supplier = await _load_supplier(session, tenant_id=tenant_id, supplier_id=payload.supplier_id)
    portal = await _load_portal(session, portal_id=payload.portal_id)
    _validate_portal_supported(portal)
    consent = await _load_consent(
        session,
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        consent_record_id=payload.consent_record_id,
    )
    _validate_consent_covers_portal(consent, portal)

    submission = SupplierSubmission(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        status=SubmissionStatus.QUEUED,
        payload_json=dict(payload.payload or {}),
        attempt_count=0,
        consent_record_id=consent.id,
    )
    session.add(submission)
    await session.flush()
    await session.refresh(submission)

    _logger.info(
        "submission_created",
        tenant_id=tenant_id,
        submission_id=submission.id,
        supplier_id=supplier.id,
        portal_id=portal.id,
        portal_platform=PortalPlatform(portal.platform).value,
    )

    await _enqueue(submission.id, session)
    return submission


async def list_submissions(
    session: AsyncSession,
    *,
    tenant_id: str,
    status_filter: SubmissionStatus | None = None,
    supplier_id: str | None = None,
    portal_id: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> list[SupplierSubmission]:
    stmt = select(SupplierSubmission).where(SupplierSubmission.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(SupplierSubmission.status == status_filter)
    if supplier_id is not None:
        stmt = stmt.where(SupplierSubmission.supplier_id == supplier_id)
    if portal_id is not None:
        stmt = stmt.where(SupplierSubmission.portal_id == portal_id)
    stmt = stmt.order_by(SupplierSubmission.created_at.desc(), SupplierSubmission.id.desc())
    stmt = stmt.limit(_clamp_limit(limit)).offset(max(offset, 0))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_submissions(
    session: AsyncSession,
    *,
    tenant_id: str,
    status_filter: SubmissionStatus | None = None,
    supplier_id: str | None = None,
    portal_id: str | None = None,
) -> int:
    stmt = select(func.count(SupplierSubmission.id)).where(SupplierSubmission.tenant_id == tenant_id)
    if status_filter is not None:
        stmt = stmt.where(SupplierSubmission.status == status_filter)
    if supplier_id is not None:
        stmt = stmt.where(SupplierSubmission.supplier_id == supplier_id)
    if portal_id is not None:
        stmt = stmt.where(SupplierSubmission.portal_id == portal_id)
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_submission(
    session: AsyncSession,
    *,
    tenant_id: str,
    submission_id: str,
) -> SupplierSubmission:
    stmt = select(SupplierSubmission).where(
        SupplierSubmission.id == submission_id,
        SupplierSubmission.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "submission_not_found",
                "message": "Submission does not exist.",
            },
        )
    return submission


async def retry_submission(
    session: AsyncSession,
    *,
    tenant_id: str,
    submission_id: str,
) -> SupplierSubmission:
    submission = await get_submission(session, tenant_id=tenant_id, submission_id=submission_id)
    if submission.status not in _RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "submission_not_retryable",
                "message": (
                    f"Submission status '{submission.status.value}' cannot be retried; "
                    "only failed or blocked submissions are eligible."
                ),
            },
        )

    submission.status = SubmissionStatus.RETRYING
    submission.last_error = None
    submission.claimed_at = None
    submission.started_at = None
    await session.flush()
    await session.refresh(submission)

    _logger.info(
        "submission_retry_queued",
        tenant_id=tenant_id,
        submission_id=submission.id,
        attempt_count=submission.attempt_count,
    )

    await _enqueue(submission.id, session)
    return submission


async def get_receipt_for_submission(
    session: AsyncSession,
    *,
    tenant_id: str,
    submission_id: str,
) -> SubmissionReceipt:
    submission = await get_submission(session, tenant_id=tenant_id, submission_id=submission_id)
    stmt = select(SubmissionReceipt).where(
        SubmissionReceipt.submission_id == submission.id,
        SubmissionReceipt.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "receipt_not_found",
                "message": "No receipt has been issued for this submission yet.",
            },
        )
    return receipt


def serialize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Defensive copy helper exposed for routers building log metadata."""

    return dict(payload or {})
