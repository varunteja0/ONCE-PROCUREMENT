"""Operator session / refresh-token records.

Distinct from tenant-user sessions (those are stateless JWTs). The cockpit
maintains a server-side row per refresh token so we can revoke individual
operator sessions without rotating the global cockpit JWT secret.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    operator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # sha256 of the refresh token — never store the raw value
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
