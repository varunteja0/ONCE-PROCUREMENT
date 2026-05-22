from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SigningKey(Base):
    """Public half of an Ed25519 signing key, used to verify receipts.

    The private key material is *not* stored in this table — it lives in the
    ``RECEIPT_SIGNING_PRIVATE_KEY_PEM`` environment variable (and ultimately in
    a KMS). This table is purely a registry so verifiers can look up the public
    key for any historical ``signing_key_id`` even after rotation.
    """

    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    algorithm: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ed25519"
    )
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = ["SigningKey"]
