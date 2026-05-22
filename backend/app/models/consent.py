from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid


class ConsentScope(str, enum.Enum):
    READ_ONLY = "read_only"
    SUBMIT_ON_BEHALF = "submit_on_behalf"
    SUBMIT_AND_SIGN = "submit_and_sign"


class ConsentRecord(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[ConsentScope] = mapped_column(
        Enum(ConsentScope, name="consent_scope", native_enum=False, length=32),
        nullable=False,
    )
    portal_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    signed_text: Mapped[str] = mapped_column(Text, nullable=False)
    signature_b64: Mapped[str] = mapped_column(Text, nullable=False)
