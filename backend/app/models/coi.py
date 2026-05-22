from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid


class CertificateOfInsurance(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "certificates_of_insurance"
    __table_args__ = (
        Index("ix_coi_tenant_expiry", "tenant_id", "expiry_date"),
    )

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
    limit_each_occurrence: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    limit_aggregate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
