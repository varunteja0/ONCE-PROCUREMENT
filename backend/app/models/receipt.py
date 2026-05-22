from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid


class SubmissionReceipt(Base, TimestampMixin):
    __tablename__ = "submission_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("supplier_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_platform: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    tos_version_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    consent_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consent_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_b64: Mapped[str] = mapped_column(Text, nullable=False)
    public_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
