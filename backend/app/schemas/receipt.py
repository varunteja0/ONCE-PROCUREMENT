from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ReceiptRead",
    "PublicReceiptRead",
    "PublicReceiptVerifyResponse",
]


class ReceiptRead(BaseModel):
    """Tenant-scoped read projection of a SubmissionReceipt.

    Includes a stable ``verify_url`` so clients can hand a single link to
    counterparties for public verification without exposing tenant secrets.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_id: str
    submission_id: str
    portal_platform: str
    submitted_at: datetime
    payload_hash: str
    tos_version_hash: str
    consent_record_id: str
    signing_key_id: str
    signature_b64: str
    public_payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    verify_url: str


class PublicReceiptRead(BaseModel):
    """Public-safe projection — strips tenant identifiers and internal IDs.

    This is the body returned from the unauthenticated ``/verify/{receipt_id}``
    endpoint. It contains only the signed payload, signature, signing key id,
    and the verification result.
    """

    model_config = ConfigDict(from_attributes=True)

    receipt_id: str
    portal_platform: str
    submitted_at: datetime
    payload_hash: str
    tos_version_hash: str
    signing_key_id: str
    signature_b64: str
    public_payload_json: dict[str, Any] = Field(default_factory=dict)


class PublicReceiptVerifyResponse(BaseModel):
    """Envelope for the public verifier endpoint."""

    model_config = ConfigDict(from_attributes=True)

    receipt: PublicReceiptRead
    verified: bool
    public_key_b64: str | None = None
    reason: str | None = None
