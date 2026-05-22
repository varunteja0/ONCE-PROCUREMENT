"""L3.7 — Pydantic schemas for the bulk-import API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.import_job import ImportEntityType, ImportStatus

__all__ = [
    "ImportJobRead",
    "ImportJobListItem",
    "ImportJobDetail",
    "ImportRowErrorRead",
    "ImportCommitRequest",
    "ImportColumnSpec",
    "ImportColumnsResponse",
    "OnDuplicateMode",
]


OnDuplicateMode = Literal["error", "update", "skip"]


class ImportRowErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int
    column: str | None = None
    value: str | None = None
    error_code: str
    error_message: str


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    entity_type: ImportEntityType
    status: ImportStatus
    original_filename: str
    file_size_bytes: int
    total_rows: int
    valid_rows: int
    invalid_rows: int
    imported_rows: int
    on_duplicate: OnDuplicateMode = "error"
    mapping: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    last_error: str | None = None
    created_by_user_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ImportJobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: ImportEntityType
    status: ImportStatus
    original_filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    imported_rows: int
    created_at: datetime
    completed_at: datetime | None = None


class ImportJobDetail(ImportJobRead):
    """Full job + first-page error preview (UI inline rendering)."""

    errors_preview: list[ImportRowErrorRead] = Field(default_factory=list)
    error_count: int = 0


class ImportCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = Field(..., description="Must be true to commit.")


class ImportColumnSpec(BaseModel):
    field: str
    required: bool
    aliases: list[str]
    description: str
    example: str | None = None


class ImportColumnsResponse(BaseModel):
    entity_type: ImportEntityType
    columns: list[ImportColumnSpec]
