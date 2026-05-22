"""RiskSchedule model — the line-of-business-specific schedule of insured items.

A risk schedule is the spreadsheet that accompanies a submission and
enumerates the specific risks being covered:

* ``vehicle_schedule`` — VINs, year/make/model, garaging address, value
  (for Commercial Auto)
* ``location_schedule`` — addresses, building values, construction class
  (for Commercial Property)
* ``employee_schedule`` — class codes, payroll, headcount per state
  (for Workers Comp)
* ``equipment_schedule`` — descriptions, serial numbers, replacement cost
  (for Inland Marine)

We persist the heterogeneous items as a JSON list and store the canonical
SHA-256 of that list as ``items_hash`` so consumers can cheaply detect
mid-flight schedule changes (a common cause of carrier re-rates). The
``total_value_cents`` rollup is informational; consumers MUST recompute
from items for binding decisions.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["RiskSchedule"]


class RiskSchedule(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "risk_schedules"
    __table_args__ = (
        CheckConstraint(
            "expiration_date IS NULL OR expiration_date > effective_date",
            name="ck_risk_schedules_period_order",
        ),
        CheckConstraint(
            "item_count >= 0",
            name="ck_risk_schedules_item_count_nonneg",
        ),
        Index(
            "ix_risk_schedules_tenant_supplier_lob",
            "tenant_id",
            "supplier_id",
            "line_of_business",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    line_of_business: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(32), nullable=False)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    total_value_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    items_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
