"""LossRunClaim model — individual claim line item inside a LossRun.

Each row represents one claim summarized in a loss run (paid + reserves +
incurred + status). Money is stored as ``BigInteger`` cents. Rows are
immutable in spirit (we never edit a parsed claim line — we re-parse), but
no DB trigger enforces immutability because we do support re-importing
loss runs which deletes and re-inserts rows under the same ``LossRun``.
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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, _uuid

__all__ = ["LossRunClaim", "LossRunClaimStatus"]


class LossRunClaimStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    REOPENED = "reopened"
    SUBROGATED = "subrogated"
    LITIGATION = "litigation"
    DENIED = "denied"
    UNKNOWN = "unknown"


class LossRunClaim(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "loss_run_claims"
    __table_args__ = (
        Index("ix_loss_run_claims_tenant_loss_run", "tenant_id", "loss_run_id"),
        Index("ix_loss_run_claims_tenant_status", "tenant_id", "status"),
        Index("ix_loss_run_claims_loss_date", "tenant_id", "loss_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    loss_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("loss_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    claim_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    claimant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loss_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[LossRunClaimStatus] = mapped_column(
        Enum(
            LossRunClaimStatus,
            name="loss_run_claim_status",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=LossRunClaimStatus.UNKNOWN,
        index=True,
    )

    cause_of_loss: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    paid_indemnity_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    paid_expense_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserve_indemnity_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserve_expense_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    recovery_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_incurred_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
