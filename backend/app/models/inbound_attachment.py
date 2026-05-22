"""L3.9 — Inbound email attachment.

Storage is abstracted via :mod:`app.services.inbound_attachment_storage`.
``storage_url`` is opaque (``file://`` today, ``s3://`` tomorrow).
``sha256`` enables dedupe within an email and across emails.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid

__all__ = ["InboundAttachment"]


class InboundAttachment(Base):
    __tablename__ = "inbound_attachments"
    __table_args__ = (
        Index("ix_inbound_attachments_email", "inbound_email_id"),
        Index("ix_inbound_attachments_sha256", "sha256"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    inbound_email_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inbound_emails.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
