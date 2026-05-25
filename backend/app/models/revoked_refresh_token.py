"""Refresh-token revocation table.

Refresh-token rotation (RFC 6749 §10.4 / §6) requires that a refresh
token, once exchanged for a new pair, can never be reused. We store the
``jti`` of every refresh token the user has presented to ``/v1/auth/
refresh`` (along with its original ``exp``) so a stolen, replayed refresh
token returns 401 instead of silently issuing a new access token.

The row is **per-tenant** (``tenant_id``) so cleanup queries can be
tenant-scoped, but the ``jti`` is globally unique because each one is a
freshly-generated UUID.

Cleanup is the caller's responsibility: a periodic job should
``DELETE FROM revoked_refresh_tokens WHERE expires_at < now()`` since
expired tokens are already rejected by the JWT ``exp`` check and don't
need an active denylist entry.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class RevokedRefreshToken(Base):
    __tablename__ = "revoked_refresh_tokens"
    __table_args__ = (
        Index("ix_revoked_refresh_tokens_expires_at", "expires_at"),
        Index("ix_revoked_refresh_tokens_tenant_id", "tenant_id"),
        Index("ix_revoked_refresh_tokens_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # JTI is a freshly-generated UUID hex; 64 chars is generous headroom.
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Mirror of the original token's ``exp`` claim so cleanup jobs can
    # drop entries that no longer matter (JWT exp check will reject them
    # anyway).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["RevokedRefreshToken"]
