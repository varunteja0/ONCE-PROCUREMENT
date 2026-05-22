from __future__ import annotations

import base64
import binascii
import threading
from typing import Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "load_signing_key",
    "sign",
    "verify",
    "derive_public_pem",
    "get_default_signing_key",
    "reset_default_signing_key_cache",
]


_logger = get_logger(__name__)

_ED25519_SEED_LEN: Final[int] = 32

_cache_lock = threading.Lock()
_cached_key: Ed25519PrivateKey | None = None
_cached_source: str | None = None


def _looks_like_pem(text: str) -> bool:
    return "-----BEGIN" in text and "-----END" in text


def _try_load_pem(pem_text: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem_text.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(
            f"Expected Ed25519 private key, got {type(key).__name__}"
        )
    return key


def _try_load_b64_seed(b64_text: str) -> Ed25519PrivateKey:
    cleaned = "".join(b64_text.split())
    padding = (-len(cleaned)) % 4
    if padding:
        cleaned = cleaned + ("=" * padding)
    try:
        raw = base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Signing key is neither valid PEM nor base64") from exc
    if len(raw) != _ED25519_SEED_LEN:
        raise ValueError(
            f"Ed25519 raw seed must be {_ED25519_SEED_LEN} bytes, got {len(raw)}"
        )
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_signing_key(pem_or_b64: str) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM text or base64-encoded 32-byte seed.

    The input format is auto-detected: anything containing PEM armor is parsed
    as PEM, otherwise it is treated as a base64-encoded raw seed.
    """

    if not isinstance(pem_or_b64, str) or not pem_or_b64.strip():
        raise ValueError("Signing key material is empty")

    text = pem_or_b64.strip()

    if _looks_like_pem(text):
        return _try_load_pem(text)

    try:
        return _try_load_b64_seed(text)
    except ValueError:
        if _looks_like_pem(text):  # pragma: no cover - already handled above
            raise
        try:
            return _try_load_pem(text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "Signing key is neither a valid PEM Ed25519 key nor a base64-encoded 32-byte seed"
            ) from exc


def sign(key: Ed25519PrivateKey, message: bytes) -> bytes:
    """Sign *message* bytes with the given Ed25519 private key."""

    if not isinstance(message, bytes | bytearray):
        raise TypeError("message must be bytes")
    return key.sign(bytes(message))


def derive_public_pem(private_key: Ed25519PrivateKey) -> str:
    """Return the SubjectPublicKeyInfo PEM for *private_key*'s public half."""

    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def _load_public_key(public_key_pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(
            f"Expected Ed25519 public key, got {type(key).__name__}"
        )
    return key


def verify(public_key_pem: str, message: bytes, sig: bytes) -> bool:
    """Verify an Ed25519 signature. Returns ``False`` on any failure."""

    try:
        public_key = _load_public_key(public_key_pem)
    except Exception:  # noqa: BLE001
        _logger.warning("receipt_verify_public_key_invalid")
        return False

    try:
        public_key.verify(bytes(sig), bytes(message))
        return True
    except InvalidSignature:
        return False
    except Exception:  # noqa: BLE001
        _logger.warning("receipt_verify_unexpected_error", exc_info=True)
        return False


def get_default_signing_key() -> Ed25519PrivateKey:
    """Return (and cache) the signing key configured via settings."""

    global _cached_key, _cached_source

    source = settings.receipt_signing_private_key_pem
    if not source or not source.strip():
        raise RuntimeError(
            "RECEIPT_SIGNING_PRIVATE_KEY_PEM is not configured; cannot sign receipts"
        )

    with _cache_lock:
        if _cached_key is not None and _cached_source == source:
            return _cached_key
        key = load_signing_key(source)
        _cached_key = key
        _cached_source = source
        _logger.info(
            "receipt_signing_key_loaded",
            key_id=settings.receipt_signing_key_id,
        )
        return key


def reset_default_signing_key_cache() -> None:
    """Clear the cached default signing key (primarily for tests)."""

    global _cached_key, _cached_source
    with _cache_lock:
        _cached_key = None
        _cached_source = None
