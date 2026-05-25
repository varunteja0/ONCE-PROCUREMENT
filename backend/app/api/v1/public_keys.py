"""Public Ed25519 key distribution endpoint.

Exposes ``GET /v1/keys/{key_id}`` so the external verifier service (and any
third party who holds a receipt) can fetch the public half of a signing key
without authentication. Private key material is never returned — this router
reads ``public_key_pem`` only.

Keys are immutable once published (rotation issues a *new* ``key_id``), so
responses are cacheable for an hour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.signing_key import SigningKey
from app.utils.logging import get_logger

__all__ = ["router"]


_logger = get_logger(__name__)

router = APIRouter(prefix="/keys", tags=["public-keys"])

_CACHE_CONTROL = "public, max-age=3600"


class PublicKeyRead(BaseModel):
    """Public-facing view of a signing key registry row."""

    model_config = ConfigDict(from_attributes=True)

    key_id: str = Field(..., description="Stable signing-key identifier.")
    algorithm: Literal["Ed25519"] = Field(
        "Ed25519", description="Signature algorithm — always Ed25519."
    )
    public_key_pem: str = Field(
        ..., description="SubjectPublicKeyInfo PEM of the Ed25519 public key."
    )
    created_at: datetime = Field(..., description="When the key was registered.")
    status: Literal["active", "revoked"] = Field(
        ..., description="`revoked` once the key has been rotated out."
    )


def _serialize(row: SigningKey) -> PublicKeyRead:
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return PublicKeyRead(
        key_id=row.id,
        algorithm="Ed25519",
        public_key_pem=row.public_key_pem,
        created_at=created,
        status="revoked" if row.revoked_at is not None else "active",
    )


@router.get(
    "/{key_id}",
    response_model=PublicKeyRead,
    summary="Fetch a public Ed25519 signing key by id (no auth required)",
    responses={404: {"description": "No signing key with that id."}},
)
async def get_public_key(
    key_id: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PublicKeyRead:
    row = await session.get(SigningKey, key_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "signing_key_not_found",
                "message": "No public signing key with that id.",
            },
        )
    response.headers["Cache-Control"] = _CACHE_CONTROL
    _logger.info(
        "public_key_served",
        key_id=key_id,
        key_status="revoked" if row.revoked_at is not None else "active",
    )
    return _serialize(row)
