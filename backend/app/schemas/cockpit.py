from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "TenantSummary",
    "TenantListResponse",
    "CockpitAuditRead",
    "CockpitAuditListResponse",
    "ActAsRequest",
    "ActAsResponse",
    "CsrfTokenResponse",
]


class TenantSummary(BaseModel):
    """Operator-side compact view of a tenant."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime
    supplier_count: int = 0
    submission_count: int = 0
    last_activity_at: datetime | None = None


class TenantListResponse(BaseModel):
    items: list[TenantSummary]
    total: int


class CockpitAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    operator_id: str | None = None
    tenant_id_acted_as: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    ip: str | None = None
    user_agent: str | None = None
    payload_redacted: dict[str, Any] | None = None
    occurred_at: datetime


class CockpitAuditListResponse(BaseModel):
    items: list[CockpitAuditRead]
    total: int


class ActAsRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=36)


class ActAsResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    permission: str
    expires_in: int


class CsrfTokenResponse(BaseModel):
    csrf_token: str
