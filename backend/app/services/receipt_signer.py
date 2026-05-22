from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    ConsentRecord,
    Portal,
    PortalPlatform,
    SigningKey,
    SubmissionReceipt,
    SupplierSubmission,
)
from app.utils.canonical_json import canonical_json_bytes, payload_sha256
from app.utils.crypto import (
    derive_public_pem,
    get_default_signing_key,
    load_signing_key,
    sign,
    verify,
)
from app.utils.logging import get_logger

__all__ = [
    "ReceiptPayload",
    "VerifyReceiptResult",
    "sign_receipt",
    "verify_receipt",
    "get_public_key_pem",
    "load_signing_key_into_cache",
    "bootstrap_signing_key",
    "clear_public_key_cache",
]


_logger = get_logger(__name__)


class ReceiptPayload(TypedDict):
    receipt_id: str
    tenant_id: str
    supplier_id: str
    portal: str
    submission_id: str
    submitted_at: str
    payload_hash: str
    tos_version_hash: str
    consent_record_id: str


class VerifyReceiptResult(TypedDict):
    receipt: dict[str, Any]
    verified: bool
    public_key_pem: str
    signing_key_id: str


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _resolve_portal_value(platform: PortalPlatform | str) -> str:
    if isinstance(platform, PortalPlatform):
        return platform.value
    return str(platform)


async def _load_portal_platform(session: AsyncSession, portal_id: str) -> str:
    result = await session.execute(select(Portal.platform).where(Portal.id == portal_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Portal {portal_id!r} not found while signing receipt")
    return _resolve_portal_value(row)


# ---------------------------------------------------------------------------
# Signing-key registry
# ---------------------------------------------------------------------------
#
# Keys are persisted in the ``signing_keys`` table. The cache below is an
# in-process, per-key memoization so the hot verify path does not hit the DB
# for every receipt. It is keyed solely on ``key_id`` — sessions are never
# captured — so it is safe to share across requests.

_PUBLIC_KEY_CACHE: dict[str, str] = {}


def _env_derived_public_pem(key_id: str) -> str | None:
    """Derive the public PEM from ``RECEIPT_SIGNING_PRIVATE_KEY_PEM``.

    Returns ``None`` when *key_id* is not the configured key or when no key
    material is configured. Provides a hermetic fallback for tests and for the
    window before the startup bootstrap has persisted the key to the DB.

    Intentionally **not** memoized: the env var is the source of truth, and
    tests rotate it between cases. The derivation is cheap (one PEM parse +
    one public-bytes export) so per-call cost is negligible.
    """

    if key_id != settings.receipt_signing_key_id:
        return None
    pem = settings.receipt_signing_private_key_pem
    if not pem or not pem.strip():
        return None
    try:
        return derive_public_pem(load_signing_key(pem))
    except Exception:  # noqa: BLE001
        _logger.warning("receipt_signing_env_pem_invalid", key_id=key_id)
        return None


def get_public_key_pem(key_id: str) -> str | None:
    """Return the cached PEM for *key_id* or ``None`` if unknown.

    The cache is populated by :func:`load_signing_key_into_cache` (called from
    async verification paths) and :func:`bootstrap_signing_key` (called on app
    startup). Falls back to deriving from the env-var private key when the
    requested id matches the configured signing key id.
    """

    pem = _PUBLIC_KEY_CACHE.get(key_id)
    if pem:
        return pem
    return _env_derived_public_pem(key_id)


async def load_signing_key_into_cache(
    session: AsyncSession, key_id: str
) -> str | None:
    """Look up *key_id* in the ``signing_keys`` table and cache the PEM.

    Returns the cached PEM (or ``None`` when the key is unknown / revoked).
    """

    cached = _PUBLIC_KEY_CACHE.get(key_id)
    if cached:
        return cached
    result = await session.execute(
        select(SigningKey).where(SigningKey.id == key_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return _env_derived_public_pem(key_id)
    _PUBLIC_KEY_CACHE[key_id] = row.public_key_pem
    return row.public_key_pem


async def bootstrap_signing_key(session: AsyncSession) -> None:
    """Ensure the configured signing key has a row in ``signing_keys``.

    Called once on app startup. If ``RECEIPT_SIGNING_PRIVATE_KEY_PEM`` is set,
    derives the public half and inserts a row keyed on
    ``RECEIPT_SIGNING_KEY_ID``. Idempotent — does nothing if the row exists.
    """

    key_id = settings.receipt_signing_key_id
    pem = settings.receipt_signing_private_key_pem
    if not pem or not pem.strip():
        _logger.info("signing_key_bootstrap_skipped_no_private_key", key_id=key_id)
        return
    existing = await session.get(SigningKey, key_id)
    if existing is not None:
        _PUBLIC_KEY_CACHE[key_id] = existing.public_key_pem
        return
    try:
        public_pem = derive_public_pem(load_signing_key(pem))
    except Exception as exc:  # noqa: BLE001
        _logger.error(
            "signing_key_bootstrap_failed", key_id=key_id, error=str(exc)
        )
        return
    session.add(
        SigningKey(
            id=key_id,
            algorithm="ed25519",
            public_key_pem=public_pem,
            description="Bootstrapped from RECEIPT_SIGNING_PRIVATE_KEY_PEM",
        )
    )
    await session.flush()
    _PUBLIC_KEY_CACHE[key_id] = public_pem
    _logger.info("signing_key_bootstrapped", key_id=key_id)


def clear_public_key_cache() -> None:
    """Reset the in-process public-key cache. Primarily for tests."""

    _PUBLIC_KEY_CACHE.clear()


def _build_payload(
    *,
    receipt_id: str,
    submission: SupplierSubmission,
    consent: ConsentRecord,
    portal_value: str,
    submitted_at: datetime,
    payload_hash: str,
    tos_version_hash: str,
) -> ReceiptPayload:
    return ReceiptPayload(
        receipt_id=receipt_id,
        tenant_id=submission.tenant_id,
        supplier_id=submission.supplier_id,
        portal=portal_value,
        submission_id=submission.id,
        submitted_at=_iso_utc(submitted_at),
        payload_hash=payload_hash,
        tos_version_hash=tos_version_hash,
        consent_record_id=consent.id,
    )


async def sign_receipt(
    session: AsyncSession,
    *,
    submission: SupplierSubmission,
    consent: ConsentRecord,
    tos_version_hash: str,
) -> SubmissionReceipt:
    """Build, sign and stage a :class:`SubmissionReceipt` for *submission*.

    The new receipt is added to *session* but **not committed** — the caller is
    responsible for the transaction boundary.
    """

    if submission.id is None:
        raise ValueError("submission must have an id before signing a receipt")
    if consent.id is None:
        raise ValueError("consent record must have an id before signing a receipt")
    if not tos_version_hash:
        raise ValueError("tos_version_hash is required")

    portal_value = await _load_portal_platform(session, submission.portal_id)

    submitted_at = (
        submission.completed_at
        or submission.started_at
        or submission.claimed_at
        or datetime.now(tz=UTC)
    )

    payload_hash = payload_sha256(submission.payload_json or {})

    receipt = SubmissionReceipt(
        submission_id=submission.id,
        tenant_id=submission.tenant_id,
        supplier_id=submission.supplier_id,
        portal_platform=portal_value,
        submitted_at=submitted_at if submitted_at.tzinfo else submitted_at.replace(tzinfo=UTC),
        payload_hash=payload_hash,
        tos_version_hash=tos_version_hash,
        consent_record_id=consent.id,
        signing_key_id=settings.receipt_signing_key_id,
        signature_b64="",
        public_payload_json={},
    )
    session.add(receipt)
    await session.flush()

    payload = _build_payload(
        receipt_id=receipt.id,
        submission=submission,
        consent=consent,
        portal_value=portal_value,
        submitted_at=submitted_at,
        payload_hash=payload_hash,
        tos_version_hash=tos_version_hash,
    )

    canonical_bytes = canonical_json_bytes(payload)
    signing_key = get_default_signing_key()
    signature = sign(signing_key, canonical_bytes)
    signature_b64 = base64.b64encode(signature).decode("ascii")

    receipt.public_payload_json = dict(payload)
    receipt.signature_b64 = signature_b64

    _logger.info(
        "receipt_signed",
        receipt_id=receipt.id,
        submission_id=submission.id,
        tenant_id=submission.tenant_id,
        supplier_id=submission.supplier_id,
        portal=portal_value,
        signing_key_id=receipt.signing_key_id,
        payload_hash=payload_hash,
    )

    return receipt


def _coerce_payload_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("public_payload_json must be a JSON object")


async def verify_receipt(session: AsyncSession, receipt_id: str) -> VerifyReceiptResult:
    """Verify the stored signature for *receipt_id*.

    Does not raise on verification failure — returns ``verified=False`` instead.
    Raises only when the receipt itself cannot be located.
    """

    result = await session.execute(
        select(SubmissionReceipt).where(SubmissionReceipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise LookupError(f"SubmissionReceipt {receipt_id!r} not found")

    public_payload = _coerce_payload_mapping(receipt.public_payload_json)
    signing_key_id = receipt.signing_key_id

    public_key_pem = await load_signing_key_into_cache(session, signing_key_id)
    if not public_key_pem:
        _logger.warning(
            "receipt_verify_unknown_key",
            receipt_id=receipt_id,
            signing_key_id=signing_key_id,
        )
        return VerifyReceiptResult(
            receipt=public_payload,
            verified=False,
            public_key_pem="",
            signing_key_id=signing_key_id,
        )

    verified = False
    try:
        signature = base64.b64decode(receipt.signature_b64, validate=True)
    except (binascii.Error, ValueError):
        _logger.warning(
            "receipt_verify_bad_signature_b64",
            receipt_id=receipt_id,
            signing_key_id=signing_key_id,
        )
        signature = b""

    if signature:
        canonical_bytes = canonical_json_bytes(public_payload)
        verified = verify(public_key_pem, canonical_bytes, signature)

    _logger.info(
        "receipt_verified",
        receipt_id=receipt_id,
        signing_key_id=signing_key_id,
        verified=verified,
    )

    return VerifyReceiptResult(
        receipt=public_payload,
        verified=verified,
        public_key_pem=public_key_pem,
        signing_key_id=signing_key_id,
    )
