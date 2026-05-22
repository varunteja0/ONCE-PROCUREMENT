"""Pydantic schemas for the PDF-extraction API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.extraction_result import ExtractionSourceType

__all__ = [
    "ExtractionEnqueueRequest",
    "ExtractionRead",
    "ExtractionList",
    "ExtractionAcceptRequest",
    "ExtractionRejectRequest",
]


class ExtractionEnqueueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: ExtractionSourceType
    document_id: str = Field(min_length=1, max_length=36)


class ExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    source_document_type: str
    source_document_id: str
    raw_text_url: str | None = None
    extracted_fields: dict[str, Any] | None = None
    field_confidences: dict[str, float] | None = None
    warnings: list[str] | None = None
    extractor_version: str
    status: str
    error: str | None = None
    reviewed_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ExtractionList(BaseModel):
    items: list[ExtractionRead]
    total: int
    limit: int
    offset: int


class ExtractionAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, Any] = Field(default_factory=dict)


class ExtractionRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=512)
