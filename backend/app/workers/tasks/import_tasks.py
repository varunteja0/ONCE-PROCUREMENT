"""L3.7 — Celery task wrapper around the import orchestrator.

Production deployments dispatch validation / commit asynchronously so
HTTP requests aren't blocked by 100K-row spreadsheets. The task simply
delegates to :mod:`app.services.import_service`; the orchestrator owns
all real logic (state machine, chunked commits, error CSV).
"""

from __future__ import annotations

import asyncio
from typing import Any

from app import db as _db
from app.models import ImportJob, ImportStatus
from app.services import import_service
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["process_import_job"]


_logger = get_logger(__name__)


async def _run(job_id: str) -> dict[str, Any]:
    async with _db.AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return {"job_id": job_id, "status": "not_found"}
        status = job.status
        tenant_id = job.tenant_id

    if status == ImportStatus.PENDING:
        async with _db.AsyncSessionLocal() as session:
            await import_service.run_validation(
                session, tenant_id=tenant_id, job_id=job_id
            )
            await session.commit()
    elif status == ImportStatus.DRY_RUN_READY:
        await import_service.run_commit(tenant_id=tenant_id, job_id=job_id)
    else:
        return {
            "job_id": job_id,
            "status": status.value,
            "skipped": True,
            "reason": "job not in a runnable status",
        }

    async with _db.AsyncSessionLocal() as session:
        job = await session.get(ImportJob, job_id)
        return {
            "job_id": job_id,
            "status": (job.status.value if job else "missing"),
            "imported_rows": (job.imported_rows if job else 0),
        }


@celery_app.task(
    bind=True,
    name="imports.process_job",
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_import_job(self, job_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Run validation OR commit, picking the right phase from job state."""

    _logger.info("import_task_started", job_id=job_id, retries=self.request.retries)
    try:
        result = asyncio.run(_run(job_id))
    except import_service.JobNotFoundError:
        _logger.warning("import_task_job_missing", job_id=job_id)
        return {"job_id": job_id, "status": "not_found"}
    except import_service.InvalidTransitionError as exc:
        _logger.warning(
            "import_task_invalid_transition", job_id=job_id, error=str(exc)
        )
        return {"job_id": job_id, "status": "invalid_transition", "error": str(exc)}
    except Exception as exc:
        _logger.exception("import_task_failed", job_id=job_id)
        raise self.retry(exc=exc) from exc
    _logger.info("import_task_completed", **result)
    return result
