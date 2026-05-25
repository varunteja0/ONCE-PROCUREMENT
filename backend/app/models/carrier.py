"""Carrier model — insurance carrier (admitted or surplus-lines).

A ``Carrier`` is a market we submit risk to or accept policies from. It is
tenant-scoped because every MGA / agency maintains its own canonical list of
appointed markets (NAIC numbers, agent codes, contact emails). Carriers
referenced by ``Quote`` / ``Policy`` rows must belong to the same tenant.

Money columns are NOT carried on this model — those live on ``Quote`` and
``Policy``. NAIC numbers are stored as strings (preserving leading zeros).
"""

from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["Carrier", "CarrierKind", "CarrierStatus"]


class CarrierKind(str, enum.Enum):
    """Regulatory classification of the carrier in the US market."""

    ADMITTED = "admitted"
    SURPLUS_LINES = "surplus_lines"
    REINSURER = "reinsurer"
    CAPTIVE = "captive"
    OTHER = "other"


class CarrierStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Carrier(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "carriers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "naic_code", name="uq_carriers_tenant_naic"),
        Index("ix_carriers_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dba_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    naic_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    am_best_rating: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kind: Mapped[CarrierKind] = mapped_column(
        Enum(CarrierKind, name="carrier_kind", native_enum=False, length=32),
        nullable=False,
        default=CarrierKind.ADMITTED,
    )
    status: Mapped[CarrierStatus] = mapped_column(
        Enum(CarrierStatus, name="carrier_status", native_enum=False, length=16),
        nullable=False,
        default=CarrierStatus.ACTIVE,
        index=True,
    )
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    primary_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    appointment_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    states_licensed_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    lines_of_business_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
