"""ProducerLicense model — state-issued insurance producer license.

US insurance producers (agents, brokers, MGAs, adjusters) must hold a
license in every state in which they place business. Each license has an
issuing state, a license number scoped to that state, an effective +
expiration window, a license type, and an authorized lines list. The NPN
(National Producer Number) is a stable cross-state identifier issued by
NIPR.

We enforce uniqueness on ``(tenant_id, supplier_id, state, license_number)``
so the same supplier cannot accidentally have duplicate license rows for
the same state/number. The ``(tenant_id, expiration_date)`` index powers
renewal-monitor scans.
"""

from __future__ import annotations

import enum
from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["LicenseStatus", "LicenseType", "ProducerLicense"]


class LicenseType(str, enum.Enum):
    RESIDENT_PRODUCER = "resident_producer"
    NON_RESIDENT_PRODUCER = "non_resident_producer"
    SURPLUS_LINES = "surplus_lines"
    ADJUSTER = "adjuster"
    MGA = "mga"
    WHOLESALER = "wholesaler"


class LicenseStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PENDING_RENEWAL = "pending_renewal"


class ProducerLicense(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "producer_licenses"
    __table_args__ = (
        CheckConstraint(
            "expiration_date > effective_date",
            name="ck_producer_licenses_period_order",
        ),
        UniqueConstraint(
            "tenant_id",
            "supplier_id",
            "state",
            "license_number",
            name="uq_producer_licenses_tenant_supplier_state_number",
        ),
        Index(
            "ix_producer_licenses_tenant_expiration",
            "tenant_id",
            "expiration_date",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    state: Mapped[str] = mapped_column(String(2), nullable=False)
    license_number: Mapped[str] = mapped_column(String(64), nullable=False)
    license_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LicenseType.RESIDENT_PRODUCER.value,
    )
    licensee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    npn: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)

    lines_authorized: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LicenseStatus.ACTIVE.value
    )

    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
