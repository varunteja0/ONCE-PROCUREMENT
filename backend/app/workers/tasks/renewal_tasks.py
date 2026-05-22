from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

from app.db import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services import coi_monitor_service
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["scan_expiring_cois_task"]


_logger = get_logger(__name__)


async def _scan(days_ahead: int) -> dict[str, Any]:
    expiring_summaries: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as session:
        try:
            expiring = await coi_monitor_service.find_expiring(
                session, tenant_id=None, days_ahead=days_ahead
            )
            today = date.today()
            for coi in expiring:
                days_until = (coi.expiry_date - today).days
                summary: dict[str, Any] = {
                    "coi_id": coi.id,
                    "tenant_id": coi.tenant_id,
                    "supplier_id": coi.supplier_id,
                    "carrier_name": coi.carrier_name,
                    "policy_number": coi.policy_number,
                    "coverage_type": coi.coverage_type,
                    "expiry_date": coi.expiry_date.isoformat(),
                    "days_until_expiry": days_until,
                }
                expiring_summaries.append(summary)
                _logger.info(
                    "coi_renewal_alert",
                    **summary,
                )
                session.add(
                    AuditLog(
                        tenant_id=coi.tenant_id,
                        actor_user_id=None,
                        action="coi.renewal_alert",
                        resource_type="certificate_of_insurance",
                        resource_id=coi.id,
                        metadata_json=summary,
                    )
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return {
        "scanned_at": datetime.now(UTC).isoformat(),
        "days_ahead": days_ahead,
        "count": len(expiring_summaries),
        "expiring": expiring_summaries,
    }


@celery_app.task(
    bind=False,
    name="renewals.scan_expiring_cois",
    acks_late=True,
)
def scan_expiring_cois_task(days_ahead: int = 30) -> dict[str, Any]:
    """Daily sweep: find COIs expiring within ``days_ahead`` and log alerts.

    Real notification delivery (email/SMS/Slack) is wired in M2. This task
    is intentionally side-effect light: it logs structured events and
    writes ``coi.renewal_alert`` audit entries so the M2 notifier can
    replay or query them.
    """

    _logger.info("renewals_scan_started", days_ahead=days_ahead)
    try:
        result = asyncio.run(_scan(days_ahead))
    except Exception as exc:
        _logger.exception(
            "renewals_scan_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "count": 0,
        }
    _logger.info("renewals_scan_completed", count=result["count"])
    return {"status": "ok", **result}
