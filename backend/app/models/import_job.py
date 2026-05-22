"""L3.7 — Bulk import job model.

One row per uploaded spreadsheet (CSV/XLSX). Drives the two-phase import
state machine (``pending → validating → dry_run_ready → importing →
completed | failed | canceled``). The companion :class:`ImportRowError`
table holds per-row validation errors so the UI can render an inline
preview *and* let the user download a full ``errors.csv``.

The model is intentionally entity-agnostic — the polymorphic
``entity_type`` column lets us reuse the pipeline for COI, loss-run, and
producer-license bulk uploads in future drops without schema changes.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, _uuid

__all__ = ["ImportJob", "ImportEntityType", "ImportStatus"]


class ImportEntityType(str, enum.Enum):
    """Polymorphic discriminator for the target table of an import."""

    SUPPLIER = "supplier"
    COI = "coi"
    LOSS_RUN = "loss_run"
    PRODUCER_LICENSE = "producer_license"


class ImportStatus(str, enum.Enum):
    """Lifecycle of an import job — see ``import_service`` for transitions."""

    PENDING = "pending"
    VALIDATING = "validating"
    DRY_RUN_READY = "dry_run_ready"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# Terminal states that block further transitions.
TERMINAL_STATUSES: frozenset[ImportStatus] = frozenset(
    {ImportStatus.COMPLETED, ImportStatus.FAILED, ImportStatus.CANCELED}
)


class ImportJob(Base, TenantScopedMixin):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    entity_type: Mapped[ImportEntityType] = mapped_column(
        Enum(ImportEntityType, name="import_entity_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status", native_enum=False, length=32),
        nullable=False,
        default=ImportStatus.PENDING,
        index=True,
    )

    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_report_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mapping: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    on_duplicate: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
