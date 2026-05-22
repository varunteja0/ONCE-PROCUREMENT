"""Pydantic schemas for the verifier API key admin surface."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "VerifierApiKeyCreate",
    "VerifierApiKeyCreated",
    "VerifierApiKeyRead",
    "VerifierApiKeyListResponse",
    "VerifierApiKeyLookup",
    "VerifierApiKeyChargeRequest",
    "VerifierApiKeyChargeResponse",
]


class VerifierApiKeyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    # Null = inherit free-tier default (``settings.verifier_free_tier_monthly_cap``).
    # Use a large explicit cap (or 0 to mean "paid tier no hard cap") for
    # paid customers. We treat ``0`` as "metered billing, no hard cap".
    monthly_call_cap: int | None = Field(default=None, ge=0)


class VerifierApiKeyRead(BaseModel):
    """Safe-to-list representation — no plaintext, no hash."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    key_prefix: str
    monthly_call_cap: int | None
    last_used_at: datetime | None
    created_by_operator_id: str | None
    created_at: datetime
    revoked_at: datetime | None


class VerifierApiKeyCreated(VerifierApiKeyRead):
    """Returned exactly once at creation time; plaintext is never re-issued."""

    plaintext: str = Field(min_length=1)


class VerifierApiKeyListResponse(BaseModel):
    total: int
    items: list[VerifierApiKeyRead]


class VerifierApiKeyLookup(BaseModel):
    """Internal-only response for the verifier service's lookup callback."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    key_hash: str
    monthly_call_cap: int | None
    revoked_at: datetime | None


class VerifierApiKeyChargeRequest(BaseModel):
    """Plaintext key submitted by the verifier service for one auth+charge call."""

    model_config = ConfigDict(extra="forbid")

    plaintext: str = Field(min_length=1, max_length=200)


class VerifierApiKeyChargeResponse(BaseModel):
    """Successful charge result. Quota exhaustion returns HTTP 402 instead."""

    api_key_id: str
    tenant_id: str
    monthly_call_cap: int | None
    current_period_count: int
    period_month: str
