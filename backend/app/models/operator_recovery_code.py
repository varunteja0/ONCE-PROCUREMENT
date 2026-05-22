"""One-time-use recovery codes for cockpit operator MFA.

Codes are stored as sha256 hashes — the plaintext is shown to the
operator exactly once at enrollment / regeneration time. ``used_at``
flips from NULL to the consumption timestamp on first successful use;
the row is then permanently invalid (no resurrection).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid


class OperatorRecoveryCode(Base, TimestampMixin):
    __tablename__ = "operator_recovery_codes"
    __table_args__ = (
        UniqueConstraint(
            "operator_id", "code_hash", name="uq_operator_recovery_op_hash"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    operator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
