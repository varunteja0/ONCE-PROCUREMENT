"""L3.8 - Celery wrapper around the PDF-extraction orchestrator.

The HTTP layer (POST /v1/extractions/document) enqueues
``extract_document(extraction_id)``; the worker loads the PDF via the
configured loader, runs the extractor, and updates the row.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app import db as _db
from app.config import settings
from app.services import extraction_service
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["extract_document"]


_logger = get_logger(__name__)


async def _run(extraction_id: str) -> dict[str, Any]:
    async with _db.AsyncSessionLocal() as session:
        try:
            row = await extraction_service.run_extraction(
                session, extraction_id=extraction_id
            )
        except extraction_service.ExtractionNotFoundError:
            return {"extraction_id": extraction_id, "status": "not_found"}
    return {
        "extraction_id": extraction_id,
        "status": row.status,
        "fields_count": len(row.extracted_fields or {}),
        "warnings_count": len(row.warnings or []),
    }


@celery_app.task(
    bind=True,
    name="extractions.extract_document",
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=60,
    soft_time_limit=getattr(settings, "extractor_timeout_seconds", 30) + 5,
)
def extract_document(self, extraction_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run the PDF extractor against ``extraction_id`` and persist the result."""
    _logger.info(
        "extraction_task_started",
        extraction_id=extraction_id,
        retries=self.request.retries,
    )
    try:
        result = asyncio.run(_run(extraction_id))
    except Exception as exc:
        _logger.exception(
            "extraction_task_failed", extraction_id=extraction_id
        )
        raise self.retry(exc=exc) from exc
    _logger.info("extraction_task_completed", **result)
    return result
