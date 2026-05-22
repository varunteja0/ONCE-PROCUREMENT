"""L3.10 — Pydantic schemas for the tenant audit-trail API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit_export import AuditExportScope, AuditExportStatus
from app.models.audit_log import AuditActorType

__all__ = [
    "AuditActorType",
    "AuditExportScope",
    "AuditExportStatus",
    "AuditLogRead",
    "AuditLogList",
    "AuditChainBreak",
    "AuditChainVerifyResult",
    "AuditExportCreate",
    "AuditExportRead",
    "AuditExportListItem",
]


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuditLogRead(_OrmModel):
    id: str
    tenant_id: str
    actor_type: AuditActorType
    actor_id: str | None
    actor_email: str | None
    action_verb: str
    resource_type: str
    resource_id: str | None
    resource_label: str | None
    request_id: str | None
    ip: str | None
    user_agent: str | None
    occurred_at: datetime
    payload_summary: dict[str, Any] | None
    prev_hash: str
    this_hash: str
    chain_position: int
    signature_key_id: str | None
    signature_b64: str | None


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int


class AuditChainBreak(BaseModel):
    chain_position: int
    row_id: str
    expected_prev_hash: str
    actual_prev_hash: str
    expected_this_hash: str
    actual_this_hash: str
    reason: Literal["prev_hash_mismatch", "this_hash_mismatch", "position_gap"]


class AuditChainVerifyResult(BaseModel):
    valid: bool
    tenant_id: str
    rows_checked: int
    from_position: int
    to_position: int
    breaks: list[AuditChainBreak]


class AuditExportCreate(BaseModel):
    scope: AuditExportScope
    scope_params: dict[str, Any] = Field(default_factory=dict)


class AuditExportRead(_OrmModel):
    id: str
    tenant_id: str
    scope_type: AuditExportScope
    scope_params: dict[str, Any] | None
    requested_by_user_id: str | None
    requested_at: datetime
    status: AuditExportStatus
    file_path: str | None
    file_sha256: str | None
    signed_envelope_path: str | None
    envelope_sha256: str | None
    expires_at: datetime | None
    row_count: int | None
    error: str | None
    completed_at: datetime | None


class AuditExportListItem(_OrmModel):
    id: str
    scope_type: AuditExportScope
    scope_params: dict[str, Any] | None
    status: AuditExportStatus
    requested_at: datetime
    completed_at: datetime | None
    row_count: int | None
    expires_at: datetime | None
    error: str | None
