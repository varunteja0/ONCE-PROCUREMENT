"""Verifier API key — tenant-scoped credentials for the public verify service.

Each row authorizes the holder of the matching plaintext secret to call the
public verifier at sustained volume above the unauthenticated per-IP burst
caps. Plaintext is shown ONCE on creation and never persisted; the table
only stores the public ``key_prefix`` (for lookup) and a SHA-256 ``key_hash``
(for constant-time comparison).

Tenant-scoped per CONTRACTS §3 (`tenant_id`, FK CASCADE). Schema is
SQLite-portable — no native enums, no JSONB, no partial indexes; PK is
``String(36)`` with a Python-side UUID default.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _uuid


class VerifierApiKey(Base):
    """Hashed verifier API key owned by a tenant."""

    __tablename__ = "verifier_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Operator-supplied label, e.g. "Acme reinsurance gateway".
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # First 12 chars of the plaintext (always starts with ``vk_live_``);
    # safe to log and store unhashed because it does not authenticate on
    # its own — the SHA-256 of the FULL plaintext is the secret.
    key_prefix: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True
    )
    # SHA-256 hex digest of the full plaintext key. 64 ASCII chars.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Monthly call cap; ``None`` means metered-billing (no hard cap).
    # Hard 402 once exceeded.
    monthly_call_cap: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_operator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["VerifierApiKey"]
