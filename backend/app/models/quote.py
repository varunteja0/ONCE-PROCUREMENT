"""Quote model — carrier-issued indication or firm quote for a supplier risk.

A ``Quote`` ties together a ``Supplier`` (the insured), a ``Carrier``, and an
optional ``SupplierSubmission`` (the outbound submission that produced it).
Money is stored as ``BigInteger`` cents — never floats. The full per-line
coverage breakdown lives in ``coverages_json`` so we can carry arbitrary
ACORD line structures without schema thrash.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["Quote", "QuoteStatus"]


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    INDICATION = "indication"
    FIRM = "firm"
    BOUND = "bound"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class Quote(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "quotes"
    __table_args__ = (
        Index("ix_quotes_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_quotes_tenant_carrier", "tenant_id", "carrier_id"),
        Index("ix_quotes_tenant_status", "tenant_id", "status"),
        Index("ix_quotes_effective", "tenant_id", "effective_date"),
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
    submission_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("supplier_submissions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    quote_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    line_of_business: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus, name="quote_status", native_enum=False, length=16),
        nullable=False,
        default=QuoteStatus.DRAFT,
        index=True,
    )

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    premium_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fees_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    taxes_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    commission_basis_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    coverages_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    terms_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
