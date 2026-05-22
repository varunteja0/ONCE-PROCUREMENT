"""L3.10 — Sign the canonical-JSON envelope wrapping an audit export.

Reuses the receipt signing infrastructure (Ed25519 key registry +
canonical-JSON encoder) so any tool that already verifies submission
receipts can verify audit envelopes with zero additional code.

Envelope contract (matches docs/AUDIT.md):

    {
      "version": "1.0",
      "tenant_id": str,
      "scope": {...},
      "generated_at": ISO8601-UTC,
      "row_count": int,
      "rows": [{ id, this_hash, occurred_at, action_verb, ... }, ...],
      "pdf_sha256": hex,
      "first_chain_hash": hex | null,
      "last_chain_hash":  hex | null,
      "signature_key_id": str,
      "signature_b64":    base64,
    }

The signature covers the canonical JSON of the envelope with
``signature_key_id`` and ``signature_b64`` removed. This mirrors the
receipt signer's pattern of signing payload-without-signature.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

from app.config import settings
from app.utils.canonical_json import canonical_json_bytes
from app.utils.crypto import (
    derive_public_pem,
    get_default_signing_key,
    sign,
    verify,
)

__all__ = [
    "ENVELOPE_VERSION",
    "sign_envelope",
    "verify_envelope",
    "envelope_signing_payload",
]


ENVELOPE_VERSION: str = "1.0"


def envelope_signing_payload(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Strip signature fields and return the canonical payload to sign."""

    return {
        k: v for k, v in envelope.items() if k not in {"signature_key_id", "signature_b64"}
    }


def sign_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Sign *envelope* in-place and return it with the signature fields set."""

    payload = envelope_signing_payload(envelope)
    canonical = canonical_json_bytes(payload)
    key = get_default_signing_key()
    signature = sign(key, canonical)
    envelope["signature_key_id"] = settings.receipt_signing_key_id
    envelope["signature_b64"] = base64.b64encode(signature).decode("ascii")
    return envelope


def verify_envelope(envelope: Mapping[str, Any], *, public_key_pem: str | None = None) -> bool:
    """Verify a signed envelope. Returns ``False`` on any failure."""

    sig_b64 = envelope.get("signature_b64")
    if not isinstance(sig_b64, str) or not sig_b64:
        return False
    try:
        signature = base64.b64decode(sig_b64, validate=True)
    except Exception:  # noqa: BLE001
        return False
    payload = envelope_signing_payload(envelope)
    canonical = canonical_json_bytes(payload)
    if public_key_pem is None:
        try:
            public_key_pem = derive_public_pem(get_default_signing_key())
        except Exception:  # noqa: BLE001
            return False
    return verify(public_key_pem, canonical, signature)
