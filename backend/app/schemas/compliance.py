"""Pydantic schemas for the SOC 2 cockpit / compliance surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AuditExportRow",
    "AuditExportResponse",
    "AccessReviewUser",
    "AccessReviewResponse",
    "AuditHashDigestRead",
    "AuditHashDigestListResponse",
    "KeyRotationCreate",
    "KeyRotationRead",
    "KeyRotationListResponse",
    "TenantDeletionRequest",
    "TenantDeletionReceipt",
]


# ---------------------------------------------------------------------------
# Audit export
# ---------------------------------------------------------------------------


class AuditExportRow(BaseModel):
    """One serialized ``AuditLog`` row, suitable for JSON Lines streaming."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata_json: dict[str, Any] | None
    ip_address: str | None
    occurred_at: datetime


class AuditExportResponse(BaseModel):
    """Wrapper used for the ``application/json`` (non-streaming) variant."""

    tenant_id: str
    start: datetime
    end: datetime
    total: int
    items: list[AuditExportRow]


# ---------------------------------------------------------------------------
# Access review
# ---------------------------------------------------------------------------


class AccessReviewUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    full_name: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    role: str
    tenant_user_id: str


class AccessReviewResponse(BaseModel):
    tenant_id: str
    generated_at: datetime
    total: int
    items: list[AccessReviewUser]


# ---------------------------------------------------------------------------
# Audit hash digests (chain inspection)
# ---------------------------------------------------------------------------


class AuditHashDigestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    covers_date: datetime
    digest_sha256: str
    prev_digest_sha256: str
    row_count: int
    computed_at: datetime


class AuditHashDigestListResponse(BaseModel):
    tenant_id: str
    total: int
    items: list[AuditHashDigestRead]


# ---------------------------------------------------------------------------
# Key rotation log
# ---------------------------------------------------------------------------


class KeyRotationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    key_name: str = Field(min_length=1, max_length=64)
    new_key_id: str | None = Field(default=None, max_length=36)
    previous_key_id: str | None = Field(default=None, max_length=36)
    notes: str = Field(min_length=1, max_length=1024)
    metadata_json: dict[str, Any] | None = None


class KeyRotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key_name: str
    new_key_id: str | None
    previous_key_id: str | None
    rotated_by_operator_id: str | None
    notes: str | None
    metadata_json: dict[str, Any] | None
    rotated_at: datetime


class KeyRotationListResponse(BaseModel):
    total: int
    items: list[KeyRotationRead]


# ---------------------------------------------------------------------------
# Tenant deletion
# ---------------------------------------------------------------------------


class TenantDeletionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=10, max_length=1024)
    confirm_tenant_slug: str = Field(min_length=1, max_length=64)


class TenantDeletionReceipt(BaseModel):
    tenant_id: str
    tenant_slug: str
    deleted_at: datetime
    row_counts: dict[str, int]
    audit_log_id: str
