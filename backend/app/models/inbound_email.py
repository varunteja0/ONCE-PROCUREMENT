"""L3.9 — Inbound email envelope.

One row per email accepted by the inbound pipeline (postmark webhook or
IMAP poll). Email body + attachments are stored in
:mod:`app.services.inbound_attachment_storage` (provider-agnostic), with
URLs persisted here.

Idempotency is enforced via ``UNIQUE(message_id)`` so duplicate webhook
deliveries (Postmark retries on 5xx) collapse to no-ops.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, _uuid

__all__ = ["InboundEmail", "InboundEmailStatus"]


class InboundEmailStatus(str, enum.Enum):
    RECEIVED = "received"
    PARSING = "parsing"
    ROUTED = "routed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class InboundEmail(Base, TenantScopedMixin):
    __tablename__ = "inbound_emails"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_inbound_emails_message_id"),
        Index("ix_inbound_emails_tenant_status", "tenant_id", "status"),
        Index("ix_inbound_emails_tenant_received", "tenant_id", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(String(998), nullable=False)
    in_reply_to: Mapped[str | None] = mapped_column(String(998), nullable=True)

    from_address: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_address: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    cc_addresses: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    raw_body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    spam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[InboundEmailStatus] = mapped_column(
        Enum(InboundEmailStatus, name="inbound_email_status", native_enum=False, length=32),
        nullable=False,
        default=InboundEmailStatus.RECEIVED,
        index=True,
    )
    routing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    draft_submission_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("supplier_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_supplier_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_storage_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
