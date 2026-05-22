"""Per-key, per-month verifier API call counter.

One row per ``(api_key_id, period_month)`` tuple. Incremented atomically
by the backend's internal ``/v1/internal/verifier-keys/charge`` endpoint
when the public verifier authenticates a call. Keeps the verifier
microservice stateless per ``verifier/AGENTS.md``.

SQLite-portable per CONTRACTS §3 — no native enums, no JSONB, no partial
indexes. PK is ``String(36)`` with a Python-side UUID default.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class VerifierApiKeyUsage(Base):
    """Monthly call counter for a single verifier API key."""

    __tablename__ = "verifier_api_key_usage"
    __table_args__ = (
        UniqueConstraint(
            "api_key_id",
            "period_month",
            name="uq_verifier_api_key_usage_key_month",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    api_key_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("verifier_api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ISO 8601 year-month, e.g. ``"2026-05"``. Stored as ASCII so it's
    # portable across SQLite and Postgres without date-truncation
    # function differences.
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


__all__ = ["VerifierApiKeyUsage"]
