from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid


class SubmissionStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED = "blocked"
    PLATFORM_UNSUPPORTED = "platform_unsupported"


class SupplierSubmission(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "supplier_submissions"
    __table_args__ = (
        Index("ix_supplier_submissions_tenant_status", "tenant_id", "status"),
        Index("ix_supplier_submissions_supplier_status", "supplier_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status", native_enum=False, length=32),
        nullable=False,
        default=SubmissionStatus.QUEUED,
        index=True,
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_record_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("consent_records.id", ondelete="SET NULL"),
        nullable=True,
    )
