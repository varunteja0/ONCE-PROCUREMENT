from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services import sanctions_service
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["refresh_ofac_task"]


_logger = get_logger(__name__)


@celery_app.task(
    bind=False,
    name="sanctions.refresh_ofac",
    acks_late=True,
)
def refresh_ofac_task() -> dict[str, Any]:
    """Refresh the in-memory OFAC SDN cache from Treasury.

    Resilient to network failure: ``sanctions_service.refresh_ofac_sdn_list``
    returns ``0`` rather than raising on any download/parse error. The
    network call is suppressed under ``APP_ENV=test``/pytest so unit tests
    stay hermetic.
    """

    started_at = datetime.now(UTC)
    _logger.info("sanctions_refresh_started", at=started_at.isoformat())
    try:
        count = sanctions_service.refresh_ofac_sdn_list()
    except Exception as exc:
        _logger.exception(
            "sanctions_refresh_unhandled_error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "count": 0,
        }

    finished_at = datetime.now(UTC)
    _logger.info(
        "sanctions_refresh_completed",
        count=count,
        duration_sec=(finished_at - started_at).total_seconds(),
    )
    return {
        "status": "ok",
        "count": count,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
