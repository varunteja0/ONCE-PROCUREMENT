"""Policy model — bound coverage between an insured (Supplier) and a Carrier.

A ``Policy`` is what a ``Quote`` becomes once bound. It carries the policy
number issued by the carrier, the in-force window, and the booked premium.
Cancellation / non-renewal events update ``status`` and write a row to the
audit trail; the policy row itself is never deleted (legal record).
"""

from __future__ import annotations

import enum
from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["Policy", "PolicyStatus"]


class PolicyStatus(str, enum.Enum):
    PENDING = "pending"
    IN_FORCE = "in_force"
    CANCELLED = "cancelled"
    NON_RENEWED = "non_renewed"
    EXPIRED = "expired"
    LAPSED = "lapsed"


class Policy(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "carrier_id",
            "policy_number",
            name="uq_policies_tenant_carrier_number",
        ),
        Index("ix_policies_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_policies_tenant_status", "tenant_id", "status"),
        Index("ix_policies_expiration", "tenant_id", "expiration_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    carrier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("carriers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quote_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("quotes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    policy_number: Mapped[str] = mapped_column(String(128), nullable=False)
    line_of_business: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, name="policy_status", native_enum=False, length=16),
        nullable=False,
        default=PolicyStatus.PENDING,
        index=True,
    )

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bound_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancelled_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    premium_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fees_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    taxes_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    coverages_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    endorsements_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
