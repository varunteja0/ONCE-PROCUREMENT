"""LossRun model — carrier-generated claims-history report for a supplier.

A loss run is the PDF (or structured export) a carrier returns to a producer
summarizing claims activity for a given policy/line over a stated period.
MGAs upload these when submitting risk to *new* carriers so the new carrier
can underwrite the account. We persist normalized aggregate metrics
(premium / paid / incurred / claim count) so dashboards and renewal
heuristics can run without re-parsing the PDF.

Money is always stored as ``BigInteger`` cents — never floats. The optional
``file_id`` / ``file_sha256`` columns let us later attach to a centralized
``files`` table (planned); for now the ``file_id`` is an opaque string that
the application treats as a future FK.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["LineOfBusiness", "LossRun", "LossRunStatus"]


class LineOfBusiness(str, enum.Enum):
    """Canonical US P&C lines used across LossRun / RiskSchedule / ACORD."""

    COMMERCIAL_AUTO = "commercial_auto"
    GENERAL_LIABILITY = "general_liability"
    WORKERS_COMP = "workers_comp"
    COMMERCIAL_PROPERTY = "commercial_property"
    UMBRELLA = "umbrella"
    PROFESSIONAL_LIABILITY = "professional_liability"
    CYBER = "cyber"
    INLAND_MARINE = "inland_marine"
    CRIME = "crime"
    OTHER = "other"


class LossRunStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    ERROR = "error"


class LossRun(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "loss_runs"
    __table_args__ = (
        CheckConstraint(
            "period_end > period_start",
            name="ck_loss_runs_period_order",
        ),
        Index("ix_loss_runs_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_loss_runs_period_end", "tenant_id", "period_end"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    carrier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    line_of_business: Mapped[str] = mapped_column(String(64), nullable=False)

    total_premium_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_incurred_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_paid_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    claim_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LossRunStatus.UPLOADED.value
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
