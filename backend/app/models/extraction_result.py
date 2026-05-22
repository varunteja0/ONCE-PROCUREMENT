"""L3.8 — PDF metadata extraction results.

One row per extraction attempt against a source document (COI, E&O
certificate, or producer license PDF). Holds the extracted fields, the
per-field confidence scores, and a small state machine so the UI can
poll for "pending → succeeded / partial / failed" and so a user can
accept (apply to the source document) or reject (flag for future model
improvement) the extraction.

The extractor implementations live under
``app.services.pdf_extraction``. This module is a dumb persistence
layer with no business logic — see :mod:`app.services.extraction_service`
for the orchestrator.
"""

from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = [
    "ExtractionResult",
    "ExtractionSourceType",
    "ExtractionStatus",
]


class ExtractionSourceType(str, enum.Enum):
    COI = "coi"
    EO_CERTIFICATE = "eo_certificate"
    PRODUCER_LICENSE = "producer_license"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ExtractionResult(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "extraction_results"
    __table_args__ = (
        Index(
            "ix_extraction_results_tenant_source",
            "tenant_id",
            "source_document_type",
            "source_document_id",
        ),
        Index(
            "ix_extraction_results_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    source_document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Optional pointer to where the raw text dump landed (S3 key, local path,
    # whatever the storage backend produces). Kept Optional so we can run
    # entirely in-memory in tests.
    raw_text_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # JSON blobs — SQLite-portable per CONTRACTS.md §2.
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    field_confidences: Mapped[dict[str, float] | None] = mapped_column(
        JSON, nullable=True
    )
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ExtractionStatus.PENDING.value
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional FK to the user that accepted / rejected (set when status moves
    # to ACCEPTED or REJECTED). Nullable + SET NULL to keep history if the
    # user is later deleted.
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
