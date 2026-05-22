from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["SigningKeyRead", "SigningKeyCreate"]


class SigningKeyRead(BaseModel):
    """Public-safe projection of a registered signing key."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    algorithm: str
    public_key_pem: str
    description: str | None = None
    created_at: datetime
    revoked_at: datetime | None = None


class SigningKeyCreate(BaseModel):
    """Payload accepted when registering a new signing key out-of-band."""

    id: str = Field(min_length=1, max_length=36)
    algorithm: str = Field(default="ed25519", max_length=16)
    public_key_pem: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=255)
