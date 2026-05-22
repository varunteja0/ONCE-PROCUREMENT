from __future__ import annotations

import asyncio
from typing import Any

from celery import Task
from celery.exceptions import Ignore, Reject, Retry

from app.db import AsyncSessionLocal
from app.services.exceptions import (
    OnceError,
    PortalRateLimited,
    PortalTransientError,
    SubmissionNotClaimable,
)
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["process_submission_task"]


_logger = get_logger(__name__)


_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    PortalTransientError,
    PortalRateLimited,
    ConnectionError,
    TimeoutError,
)


async def _run(submission_id: str) -> dict[str, Any]:
    """Open a fresh AsyncSession and delegate to the pipeline."""

    from app.services.submission_pipeline import process_submission

    async with AsyncSessionLocal() as session:
        try:
            result = await process_submission(submission_id, session=session)
        except Exception:
            await session.rollback()
            raise
        return {
            "status": result.status.value,
            "receipt_id": result.receipt_id,
            "error": result.error,
            "result_payload": result.result_payload,
        }


@celery_app.task(
    bind=True,
    name="submissions.process",
    acks_late=True,
    autoretry_for=(),
    max_retries=3,
)
def process_submission_task(self: Task, submission_id: str) -> dict[str, Any]:
    """Celery entry point for ``submission_pipeline.process_submission``.

    Catches and logs all exceptions. Only retries on transient errors
    (network/portal-transient/rate-limit); all other failures are terminal
    so the pipeline's recorded ``SubmissionStatus`` remains authoritative.
    """

    log = _logger.bind(submission_id=submission_id, task_id=self.request.id)
    log.info("submission_task_started", attempt=self.request.retries + 1)

    try:
        payload = asyncio.run(_run(submission_id))
    except SubmissionNotClaimable as exc:
        log.info("submission_task_not_claimable", reason=str(exc))
        return {
            "status": "skipped",
            "reason": "not_claimable",
            "message": exc.message,
            "context": exc.context,
        }
    except _TRANSIENT_EXCEPTIONS as exc:
        log.warning(
            "submission_task_transient_error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc
    except (Retry, Ignore, Reject):
        raise
    except OnceError as exc:
        log.error(
            "submission_task_domain_error",
            error_type=type(exc).__name__,
            error=str(exc),
            context=exc.context,
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": exc.message,
            "context": exc.context,
        }
    except Exception as exc:
        log.exception(
            "submission_task_unhandled_error",
            error_type=type(exc).__name__,
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }

    log.info(
        "submission_task_completed",
        status=payload.get("status"),
        receipt_id=payload.get("receipt_id"),
    )
    return payload
