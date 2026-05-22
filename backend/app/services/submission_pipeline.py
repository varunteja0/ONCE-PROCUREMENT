from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConsentRecord,
    ConsentScope,
    Portal,
    PortalPlatform,
    SubmissionStatus,
    Supplier,
    SupplierSubmission,
)
from app.services.exceptions import (
    ConsentMissing,
    OnceError,
    PortalCaptcha,
    PortalPermanentError,
    PortalRateLimited,
    PortalTransientError,
    PortalUnsupported,
    SubmissionNotClaimable,
    SubmitterNotFound,
)
from app.utils.canonical_json import payload_sha256
from app.utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.automation.base import BaseSubmitter


__all__ = ["SubmissionResult", "process_submission"]


_logger = get_logger(__name__)

MAX_ATTEMPTS: int = 5
"""Maximum number of attempts before a transient failure becomes terminal."""

_WRITE_CONSENT_SCOPES: frozenset[ConsentScope] = frozenset(
    {ConsentScope.SUBMIT_ON_BEHALF, ConsentScope.SUBMIT_AND_SIGN}
)


@dataclass(slots=True)
class SubmissionResult:
    """Outcome of a single ``process_submission`` invocation."""

    status: SubmissionStatus
    receipt_id: str | None
    error: str | None
    result_payload: dict[str, Any] | None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _serialize_outcome(outcome: Any) -> dict[str, Any]:
    """Best-effort serialization of a ``SubmitterOutcome`` for ``result_json``."""

    if outcome is None:
        return {}
    if is_dataclass(outcome) and not isinstance(outcome, type):
        try:
            return asdict(outcome)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("submission_outcome_asdict_failed", error=str(exc))
    payload = getattr(outcome, "result", None)
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(outcome, "__dict__"):
        return {k: v for k, v in vars(outcome).items() if not k.startswith("_")}
    return {}


def _get_submitter(platform: PortalPlatform) -> BaseSubmitter:
    """Resolve the submitter for ``platform`` via lazy import.

    The automation package is imported lazily because it pulls in Playwright
    and platform-specific dependencies that should not be required to import
    the pipeline (or the API layer) in test contexts.
    """

    try:
        from app.automation.submitters import get_submitter as _registry_lookup
    except ImportError as exc:  # pragma: no cover - automation pkg optional in tests
        raise SubmitterNotFound(
            "Automation submitter registry is unavailable.",
            platform=platform.value,
            cause=str(exc),
        ) from exc

    try:
        submitter = _registry_lookup(platform)
    except KeyError as exc:
        raise SubmitterNotFound(
            "No submitter is registered for portal platform.",
            platform=platform.value,
        ) from exc

    if submitter is None:
        raise SubmitterNotFound(
            "No submitter is registered for portal platform.",
            platform=platform.value,
        )
    return submitter


async def _claim_submission(
    session: AsyncSession, submission_id: str
) -> SupplierSubmission:
    """Atomically transition QUEUED|RETRYING → RUNNING and return the row.

    Implements the contract in CONTRACTS.md §5: a single UPDATE that gates on
    the prior status and returns the freshly-claimed row. If zero rows match
    (already running, completed, blocked, etc.) ``SubmissionNotClaimable`` is
    raised so callers can no-op safely in the face of duplicate dispatch.
    """

    now = _utcnow()
    stmt = (
        update(SupplierSubmission)
        .where(
            SupplierSubmission.id == submission_id,
            SupplierSubmission.status.in_(
                [SubmissionStatus.QUEUED, SubmissionStatus.RETRYING]
            ),
        )
        .values(
            status=SubmissionStatus.RUNNING,
            claimed_at=now,
            started_at=now,
            attempt_count=SupplierSubmission.attempt_count + 1,
            last_error=None,
        )
        .execution_options(synchronize_session="fetch")
    )
    result = await session.execute(stmt)

    if (result.rowcount or 0) != 1:
        raise SubmissionNotClaimable(
            "Submission could not be claimed; not in a claimable status.",
            submission_id=submission_id,
        )

    submission = await session.get(SupplierSubmission, submission_id)
    if submission is None:  # pragma: no cover - cannot happen if rowcount == 1
        raise SubmissionNotClaimable(
            "Submission disappeared after claim.",
            submission_id=submission_id,
        )
    await session.refresh(submission)
    return submission


async def _load_related(
    session: AsyncSession, submission: SupplierSubmission
) -> tuple[Supplier, Portal, ConsentRecord | None]:
    supplier = await session.get(Supplier, submission.supplier_id)
    portal = await session.get(Portal, submission.portal_id)
    consent: ConsentRecord | None = None
    if submission.consent_record_id is not None:
        consent = await session.get(ConsentRecord, submission.consent_record_id)

    if supplier is None:
        raise PortalPermanentError(
            "Supplier referenced by submission no longer exists.",
            submission_id=submission.id,
            supplier_id=submission.supplier_id,
        )
    if portal is None:
        raise PortalPermanentError(
            "Portal referenced by submission no longer exists.",
            submission_id=submission.id,
            portal_id=submission.portal_id,
        )
    return supplier, portal, consent


def _validate_portal(portal: Portal) -> None:
    if not portal.is_supported:
        raise PortalUnsupported(
            "Portal is not supported for automated submission.",
            portal_id=portal.id,
            platform=PortalPlatform(portal.platform).value,
        )


def _validate_consent(consent: ConsentRecord | None, portal: Portal) -> ConsentRecord:
    if consent is None:
        raise ConsentMissing(
            "Submission has no associated consent record.",
            portal_id=portal.id,
        )
    if consent.revoked_at is not None:
        raise ConsentMissing(
            "Consent record has been revoked.",
            consent_id=consent.id,
            revoked_at=consent.revoked_at.isoformat(),
        )
    if consent.scope not in _WRITE_CONSENT_SCOPES:
        raise ConsentMissing(
            "Consent scope does not authorize submitting on behalf of supplier.",
            consent_id=consent.id,
            scope=consent.scope.value,
        )
    portal_ids = list(consent.portal_ids_json or [])
    if portal_ids and "*" not in portal_ids and portal.id not in portal_ids:
        raise ConsentMissing(
            "Consent record does not cover the requested portal.",
            consent_id=consent.id,
            portal_id=portal.id,
        )
    return consent


def _derive_tos_version_hash(portal: Portal) -> str:
    """Deterministic placeholder ToS hash until per-portal ToS capture lands.

    The Portal model does not yet persist ToS text, so we derive a stable
    per-portal value so receipts remain verifiable and unique-per-portal.
    """

    return "sha256:" + payload_sha256(
        {
            "portal_id": portal.id,
            "portal_platform": PortalPlatform(portal.platform).value,
            "tos_capture_version": "v0",
        }
    )


async def _sign_receipt(
    *,
    session: AsyncSession,
    submission: SupplierSubmission,
    portal: Portal,
    consent: ConsentRecord,
) -> str | None:
    """Invoke the receipt signer if available; return the new receipt id."""

    try:
        from app.services import receipt_signer  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - signer optional in early bring-up
        _logger.warning(
            "receipt_signer_unavailable",
            submission_id=submission.id,
        )
        return None

    sign: Callable[..., Awaitable[Any]] | None = getattr(
        receipt_signer, "sign_receipt", None
    )
    if sign is None:  # pragma: no cover - defensive
        _logger.warning(
            "receipt_signer_missing_sign_receipt",
            submission_id=submission.id,
        )
        return None

    receipt = await sign(
        session,
        submission=submission,
        consent=consent,
        tos_version_hash=_derive_tos_version_hash(portal),
    )
    return getattr(receipt, "id", None)


def _classify_failure(
    exc: BaseException, attempt_count: int
) -> tuple[SubmissionStatus, str]:
    """Map a raised exception to (next_status, last_error_string)."""

    if isinstance(exc, PortalCaptcha):
        return SubmissionStatus.BLOCKED, str(exc)
    if isinstance(exc, PortalRateLimited | PortalTransientError):
        if attempt_count < MAX_ATTEMPTS:
            return SubmissionStatus.RETRYING, str(exc)
        return SubmissionStatus.FAILED, (
            f"max_attempts_exceeded ({attempt_count}/{MAX_ATTEMPTS}): {exc}"
        )
    if isinstance(exc, PortalUnsupported):
        return SubmissionStatus.PLATFORM_UNSUPPORTED, str(exc)
    if isinstance(exc, PortalPermanentError | ConsentMissing | SubmitterNotFound):
        return SubmissionStatus.FAILED, str(exc)
    if isinstance(exc, OnceError):
        return SubmissionStatus.FAILED, str(exc)
    return SubmissionStatus.FAILED, f"{type(exc).__name__}: {exc}"


async def process_submission(
    submission_id: str, session: AsyncSession
) -> SubmissionResult:
    """Atomically claim, dispatch, and finalize a supplier submission.

    See ``CONTRACTS.md`` §5 for the contract. This function is the *single*
    canonical entry point for executing a submission; both the in-process
    dispatcher (``submission_service._enqueue``) and the Celery worker task
    funnel here.
    """

    log = _logger.bind(submission_id=submission_id)

    submission = await _claim_submission(session, submission_id)
    log = log.bind(
        tenant_id=submission.tenant_id,
        supplier_id=submission.supplier_id,
        portal_id=submission.portal_id,
        attempt=submission.attempt_count,
    )
    log.info("submission_claimed")

    try:
        supplier, portal, consent_optional = await _load_related(session, submission)
        _validate_portal(portal)
        consent = _validate_consent(consent_optional, portal)
        platform = PortalPlatform(portal.platform)
        submitter = _get_submitter(platform)

        log = log.bind(platform=platform.value)
        log.info("submission_dispatching")

        outcome = await submitter.submit(
            supplier=supplier,
            portal=portal,
            payload=dict(submission.payload_json or {}),
            consent=consent,
        )
    except BaseException as exc:
        next_status, last_error = _classify_failure(exc, submission.attempt_count)
        submission.status = next_status
        submission.last_error = last_error
        submission.completed_at = (
            _utcnow() if next_status != SubmissionStatus.RETRYING else None
        )
        await session.flush()
        await session.commit()

        log.warning(
            "submission_failed",
            next_status=next_status.value,
            error_type=type(exc).__name__,
            error=last_error,
        )

        if isinstance(exc, OnceError):
            return SubmissionResult(
                status=next_status,
                receipt_id=None,
                error=last_error,
                result_payload=exc.to_dict(),
            )
        return SubmissionResult(
            status=next_status,
            receipt_id=None,
            error=last_error,
            result_payload=None,
        )

    result_payload = _serialize_outcome(outcome)
    receipt_id: str | None = None
    try:
        receipt_id = await _sign_receipt(
            session=session,
            submission=submission,
            portal=portal,
            consent=consent,
        )
    except Exception as exc:
        log.exception("receipt_signing_failed", error=str(exc))
        submission.status = SubmissionStatus.FAILED
        submission.last_error = f"receipt_signing_failed: {exc}"
        submission.completed_at = _utcnow()
        await session.flush()
        await session.commit()
        return SubmissionResult(
            status=SubmissionStatus.FAILED,
            receipt_id=None,
            error=submission.last_error,
            result_payload=result_payload,
        )

    submission.status = SubmissionStatus.COMPLETED
    submission.completed_at = _utcnow()
    submission.result_json = result_payload
    submission.last_error = None
    await session.flush()
    await session.commit()

    log.info("submission_completed", receipt_id=receipt_id)

    return SubmissionResult(
        status=SubmissionStatus.COMPLETED,
        receipt_id=receipt_id,
        error=None,
        result_payload=result_payload,
    )
