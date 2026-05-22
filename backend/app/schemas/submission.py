from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.submission import SubmissionStatus

__all__ = [
    "SubmissionCreate",
    "SubmissionRead",
    "SubmissionListItem",
]


class SubmissionCreate(BaseModel):
    """Inbound payload to enqueue a new portal submission."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    supplier_id: str = Field(min_length=1, max_length=36)
    portal_id: str = Field(min_length=1, max_length=36)
    payload: dict[str, Any] = Field(default_factory=dict)
    consent_record_id: str = Field(min_length=1, max_length=36)


class SubmissionRead(BaseModel):
    """Full read projection of a SupplierSubmission row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    portal_id: str
    status: SubmissionStatus
    payload_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] | None = None
    attempt_count: int
    last_error: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    consent_record_id: str | None = None
    created_at: datetime
    updated_at: datetime


class SubmissionListItem(BaseModel):
    """Lightweight projection for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: str
    portal_id: str
    status: SubmissionStatus
    attempt_count: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
