from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid


class CertificateOfInsurance(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "certificates_of_insurance"
    __table_args__ = (Index("ix_coi_tenant_expiry", "tenant_id", "expiry_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    supplier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    carrier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_number: Mapped[str] = mapped_column(String(128), nullable=False)
    coverage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    limit_each_occurrence: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    limit_aggregate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- ACORD-25 fidelity columns (added 2026-05-25). All nullable so legacy
    # COI rows uploaded before this expansion remain valid.
    certificate_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    producer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    producer_naic: Mapped[str | None] = mapped_column(String(16), nullable=True)
    additional_insureds_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    waiver_of_subrogation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    primary_and_noncontributory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    policy_form_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description_of_operations: Mapped[str | None] = mapped_column(Text, nullable=True)
    acord25_limits_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
