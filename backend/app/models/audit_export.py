"""L3.10 — Audit-trail export job + signed-envelope metadata."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid

__all__ = [
    "AuditExport",
    "AuditExportScope",
    "AuditExportStatus",
]


class AuditExportScope(str, enum.Enum):
    TENANT = "tenant"
    SUPPLIER = "supplier"
    SUBMISSION = "submission"
    DATE_RANGE = "date_range"


class AuditExportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class AuditExport(Base):
    __tablename__ = "audit_exports"
    __table_args__ = (
        Index(
            "ix_audit_exports_tenant_requested",
            "tenant_id",
            "requested_at",
        ),
        Index(
            "ix_audit_exports_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_type: Mapped[AuditExportScope] = mapped_column(
        SAEnum(
            AuditExportScope,
            name="audit_export_scope",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    scope_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[AuditExportStatus] = mapped_column(
        SAEnum(
            AuditExportStatus,
            name="audit_export_status",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=AuditExportStatus.PENDING,
    )

    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_envelope_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    envelope_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
