"""Public *list* endpoint for Ed25519 signing keys.

The existing :mod:`app.api.v1.public_keys` router exposes
``GET /v1/keys/{key_id}`` (single-key lookup by id). This module adds a
companion **list** endpoint so auditors and the standalone verifier can
discover every published key in one round trip, and so the keys can be
copy-pasted into a DNS TXT record for out-of-band trust distribution.

Routes (no auth, public):

* ``GET /v1/public/keys`` — JSON array of every key, both active and
  revoked. Cacheable for 1 hour (keys are immutable; rotation issues a new
  ``key_id``).
* ``GET /v1/public/keys.txt`` — plain-text, one PEM per line, suitable
  for piping into a DNS-TXT publish script (see
  ``docs/PUBLIC_TRUST_KEYS.md``).

Private key material is never read or returned.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.signing_key import SigningKey
from app.utils.logging import get_logger

__all__ = ["router"]

_logger = get_logger(__name__)

# Path-prefix matches the sibling ``public_v1_receipt_router`` so the public
# surface stays consistent: every unauthenticated, machine-readable resource
# lives under ``/v1/public/``.
router = APIRouter(prefix="/public/keys", tags=["public-keys"])

_CACHE_CONTROL = "public, max-age=3600"


class PublicKeyListItem(BaseModel):
    """One row in the public keys list response."""

    model_config = ConfigDict(from_attributes=True)

    key_id: str = Field(..., description="Stable signing-key identifier.")
    algorithm: Literal["Ed25519"] = Field("Ed25519")
    public_key_pem: str = Field(..., description="SubjectPublicKeyInfo PEM of the Ed25519 public key.")
    created_at: datetime
    status: Literal["active", "revoked"]


class PublicKeyListResponse(BaseModel):
    """Wrapper so we can add ``next_cursor`` later without breaking clients."""

    keys: list[PublicKeyListItem]
    count: int = Field(..., ge=0)


@router.get(
    "",
    response_model=PublicKeyListResponse,
    summary="List every public Ed25519 signing key (no auth required)",
)
async def list_public_keys(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    include_revoked: Annotated[
        bool,
        Query(description="Include revoked keys (default: true)."),
    ] = True,
) -> PublicKeyListResponse:
    stmt = select(SigningKey).order_by(desc(SigningKey.created_at))
    if not include_revoked:
        stmt = stmt.where(SigningKey.revoked_at.is_(None))

    rows = (await session.execute(stmt)).scalars().all()
    items = [_serialize(row) for row in rows]

    response.headers["Cache-Control"] = _CACHE_CONTROL
    _logger.info("public_keys_listed", count=len(items), include_revoked=include_revoked)
    return PublicKeyListResponse(keys=items, count=len(items))


@router.get(
    ".txt",
    response_class=PlainTextResponse,
    summary="Public keys as plain-text PEMs (for DNS TXT publication)",
    responses={200: {"content": {"text/plain": {}}}},
)
async def list_public_keys_text(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlainTextResponse:
    """Return one ``key_id\\n<PEM>\\n`` block per active key.

    The format is intentionally trivial so ``docs/PUBLIC_TRUST_KEYS.md``'s
    DNS-publication script can ``curl | awk`` it without any JSON parsing.
    """

    stmt = select(SigningKey).where(SigningKey.revoked_at.is_(None)).order_by(desc(SigningKey.created_at))
    rows = (await session.execute(stmt)).scalars().all()

    parts: list[str] = []
    for row in rows:
        parts.append(f"key_id: {row.id}")
        parts.append(row.public_key_pem.strip())
        parts.append("")  # blank line separator
    body = "\n".join(parts) + ("\n" if parts else "")

    response.headers["Cache-Control"] = _CACHE_CONTROL
    return PlainTextResponse(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


def _serialize(row: SigningKey) -> PublicKeyListItem:
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return PublicKeyListItem(
        key_id=row.id,
        algorithm="Ed25519",
        public_key_pem=row.public_key_pem,
        created_at=created,
        status="revoked" if row.revoked_at is not None else "active",
    )
