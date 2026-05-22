"""L3.6 — Email verification code storage.

Codes are stored as ``sha256(code + pepper)``. The plaintext code never
hits the database. ``pepper`` is :attr:`app.config.Settings.secret_key`.

Rate limiting and attempt limits are enforced in
:mod:`app.services.email_verification_service`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (
        Index("ix_email_verifications_email_created", "email", "created_at"),
        Index("ix_email_verifications_tenant", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


__all__ = ["EmailVerification"]
