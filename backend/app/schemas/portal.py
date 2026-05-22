from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.portal import PortalPlatform

__all__ = ["PortalRead", "PortalList"]


class PortalRead(BaseModel):
    """Read projection for a Portal entry.

    Portals form a global, read-only catalog managed out-of-band. The API
    exposes only enough metadata for tenants to choose targets and inspect
    support / risk gating decisions.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: PortalPlatform
    display_name: str
    base_url: str | None = None
    is_supported: bool
    risky: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class PortalList(BaseModel):
    """Envelope for paginated portal listings."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PortalRead]
    total: int
