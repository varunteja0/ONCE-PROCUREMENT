"""Public carrier-coverage / portal-health endpoint.

``GET /v1/public/portals`` powers the marketing-side "Carrier Coverage" page
([frontend/src/pages/public/Coverage.tsx]). No auth, no tenant context,
read-only. Backed by :mod:`app.services.portal_health_service`, which reads
the smoke-test JSON state file written by the Celery beat task.

Why public:

* Lets prospects verify carrier support without booking a demo.
* Turns the existing smoke-probe infrastructure into a competitive moat —
  no other vendor in this space exposes per-carrier observability.
* Lets the verifier microservice / auditors confirm the carrier list
  matches the receipts they see.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.services.portal_health_service import (
    PortalCoverageRow,
    load_portal_coverage,
)
from app.utils.logging import get_logger

__all__ = ["router"]

_logger = get_logger(__name__)

router = APIRouter(prefix="/public/portals", tags=["public-portals"])

# Coverage snapshots can change up to once per smoke-test interval (15 min).
# Cache for 5 minutes at the edge so the page is fast without going stale.
_CACHE_CONTROL = "public, max-age=300"


class PublicPortalCoverageItem(BaseModel):
    """One row of the public carrier-coverage table."""

    model_config = ConfigDict(from_attributes=True)

    platform: str = Field(..., description="Stable PortalPlatform enum value.")
    display_name: str = Field(..., description="Human-readable carrier name.")
    supported: bool = Field(..., description="True if a concrete submitter ships today.")
    status: Literal["healthy", "degraded", "down", "unknown"]
    last_status_change_at: datetime | None
    consecutive_failures: int = Field(..., ge=0)


class PublicPortalCoverageResponse(BaseModel):
    """Envelope so we can add aggregate metrics later (uptime %, etc.)."""

    portals: list[PublicPortalCoverageItem]
    supported_count: int = Field(..., ge=0)
    healthy_count: int = Field(..., ge=0)
    total_count: int = Field(..., ge=0)


@router.get(
    "",
    response_model=PublicPortalCoverageResponse,
    summary="Public carrier coverage + per-portal health (no auth)",
)
async def list_public_portals(response: Response) -> PublicPortalCoverageResponse:
    rows = load_portal_coverage(state_path=settings.portal_smoke_state_path)

    items = [_to_item(row) for row in rows]
    supported = sum(1 for r in rows if r.supported)
    healthy = sum(1 for r in rows if r.status == "healthy")

    response.headers["Cache-Control"] = _CACHE_CONTROL
    _logger.info(
        "public_portals_served",
        total=len(items),
        supported=supported,
        healthy=healthy,
    )
    return PublicPortalCoverageResponse(
        portals=items,
        supported_count=supported,
        healthy_count=healthy,
        total_count=len(items),
    )


def _to_item(row: PortalCoverageRow) -> PublicPortalCoverageItem:
    return PublicPortalCoverageItem(
        platform=row.platform,
        display_name=row.display_name,
        supported=row.supported,
        status=row.status,
        last_status_change_at=row.last_status_change_at,
        consecutive_failures=row.consecutive_failures,
    )
