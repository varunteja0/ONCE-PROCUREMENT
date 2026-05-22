"""EOCertificate model — Errors & Omissions insurance certificate.

E&O is professional-liability coverage that protects a producer/MGA against
claims of negligence or failure-to-perform. Carriers and many state DOIs
require proof of active E&O before appointing a producer or accepting
submissions on their behalf.

We track per-claim and aggregate limits + the deductible (all in cents),
the named insured, an optional list of additional insureds, and the
effective/expiration window. The status field powers expiry monitors.
"""

from __future__ import annotations

import enum
from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["EOCertificate", "EOCertificateStatus"]


class EOCertificateStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING_RENEWAL = "pending_renewal"


class EOCertificate(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "eo_certificates"
    __table_args__ = (
        CheckConstraint(
            "expiration_date > effective_date",
            name="ck_eo_certificates_period_order",
        ),
        CheckConstraint(
            "coverage_amount_cents >= 0",
            name="ck_eo_certificates_coverage_nonneg",
        ),
        Index(
            "ix_eo_certificates_tenant_expiration",
            "tenant_id",
            "expiration_date",
        ),
        Index(
            "ix_eo_certificates_tenant_supplier",
            "tenant_id",
            "supplier_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    carrier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_number: Mapped[str] = mapped_column(String(64), nullable=False)

    coverage_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    aggregate_amount_cents: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    deductible_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)

    named_insured: Mapped[str] = mapped_column(String(255), nullable=False)
    additional_insureds: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EOCertificateStatus.ACTIVE.value
    )

    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
