"""L3.9 — Celery tasks for inbound email pipeline.

* ``inbound.process_email`` — re-run routing for a stored email (used by
  the retry endpoint and by Postmark webhook handler for out-of-band
  processing if synchronous routing is disabled).
* ``inbound.imap_poll`` — scheduled IMAP poller. Beat-driven.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app import db as _db
from app.models import InboundEmail
from app.services import inbound_email_service
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app
from app.workers.imap_client import poll_once

__all__ = ["process_inbound_email", "imap_poll_task"]


_logger = get_logger(__name__)


async def _retry(email_id: str) -> dict[str, Any]:
    async with _db.AsyncSessionLocal() as session:
        # Pre-resolve tenant from the row so the service-layer tenant filter
        # has an authoritative tenant_id. The worker is a trusted internal
        # caller: it receives email_id from API handlers that already
        # validated tenant ownership.
        row = await session.get(InboundEmail, email_id)
        if row is None:
            return {"email_id": email_id, "ok": False, "error": "not_found"}
        tenant_id = row.tenant_id
        try:
            email = await inbound_email_service.retry_routing(
                session, tenant_id=tenant_id, email_id=email_id
            )
        except inbound_email_service.InboundIngestError as exc:
            return {"email_id": email_id, "ok": False, "error": str(exc)}
    return {"email_id": email.id, "status": email.status.value, "ok": True}


@celery_app.task(
    bind=True,
    name="inbound.process_email",
    acks_late=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_inbound_email(self, email_id: str) -> dict[str, Any]:  # type: ignore[no-redef]
    try:
        return asyncio.run(_retry(email_id))
    except Exception as exc:  # pragma: no cover - celery handles
        _logger.exception("inbound.process_email_failed", email_id=email_id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="inbound.imap_poll",
    acks_late=True,
    max_retries=0,
)
def imap_poll_task(self) -> dict[str, Any]:  # type: ignore[no-redef]
    try:
        counts = asyncio.run(poll_once())
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("inbound.imap_poll_failed", error=str(exc))
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **counts}
