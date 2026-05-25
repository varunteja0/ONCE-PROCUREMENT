"""Canonical JSON encoding for receipt signing.

Defaults to RFC 8785 (JCS) via the ``rfc8785`` package (Trail of Bits,
Apache-2.0). A second "legacy" encoder is kept solely so receipts signed
before the JCS-library cutover continue to verify (dual-encoder verify
in :func:`verify_canonical_match`). New signatures are ALWAYS produced
over RFC 8785 bytes; never over legacy bytes.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Final

import rfc8785

__all__ = [
    "canonical_json_bytes",
    "canonical_json_str",
    "payload_sha256",
    "legacy_canonical_json_bytes",
    "verify_canonical_match",
]


# ---------------------------------------------------------------------------
# NEW (default) encoder \u2014 RFC 8785 via ``rfc8785``.
# All new receipt signatures are produced over the bytes returned here.
# ---------------------------------------------------------------------------


def canonical_json_bytes(obj: Any) -> bytes:
    """Return RFC 8785 (JCS) canonical JSON UTF-8 bytes for *obj*.

    Delegates to :func:`rfc8785.dumps`. Raises
    :class:`rfc8785.CanonicalizationError` (a subclass of
    :class:`ValueError`) on any unrepresentable input \u2014 NaN, \u00b1Infinity,
    non-string object keys, unsupported Python types, or integers
    outside the IEEE-754 safe range (|n| > 2**53 - 1).
    """

    return rfc8785.dumps(obj)


def canonical_json_str(obj: Any) -> str:
    """Return RFC 8785 canonical JSON string for *obj* (UTF-8 decoded)."""

    return canonical_json_bytes(obj).decode("utf-8")


def payload_sha256(obj: Any) -> str:
    """Return hex SHA-256 digest of the canonical JSON encoding of *obj*."""

    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


# ---------------------------------------------------------------------------
# LEGACY encoder \u2014 retained ONLY so :func:`verify_canonical_match` can fall
# back when verifying receipts signed before the JCS-library cutover. Do NOT
# use this for any new signing path; new code MUST call ``canonical_json_bytes``.
#
# Byte-for-byte copy of the pre-cutover implementation.
# ---------------------------------------------------------------------------


_LEGACY_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r'[\\"\x00-\x1f]')
_LEGACY_ESCAPE_MAP: Final[dict[str, str]] = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _legacy_escape_str(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        char = match.group(0)
        mapped = _LEGACY_ESCAPE_MAP.get(char)
        if mapped is not None:
            return mapped
        return f"\\u{ord(char):04x}"

    return '"' + _LEGACY_ESCAPE_RE.sub(replace, value) + '"'


def _legacy_format_number(value: int | float) -> str:
    if isinstance(value, bool):  # pragma: no cover
        raise TypeError("bool should not reach _legacy_format_number")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("NaN and Infinity are not permitted in canonical JSON")
    if value == 0:
        return "0"
    as_int = int(value)
    if value == as_int and abs(value) < 1e16:
        return str(as_int)
    text = repr(value)
    if "e" in text or "E" in text:
        mantissa, _, exp = text.partition("e") if "e" in text else text.partition("E")
        if "." in mantissa:
            mantissa = mantissa.rstrip("0").rstrip(".")
            if mantissa in ("", "-"):
                mantissa = mantissa + "0"
        exp_int = int(exp)
        text = f"{mantissa}e{exp_int:+d}"
    elif "." in text:
        text = text.rstrip("0").rstrip(".")
        if text in ("", "-"):
            text = text + "0"
    return text


def _legacy_encode(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _legacy_format_number(value)
    if isinstance(value, str):
        return _legacy_escape_str(value)
    if isinstance(value, list | tuple):
        return "[" + ",".join(_legacy_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        items: list[tuple[str, Any]] = []
        for key, val in value.items():
            if not isinstance(key, str):
                raise TypeError(f"Canonical JSON object keys must be strings, got {type(key).__name__}")
            items.append((key, val))
        items.sort(key=lambda kv: kv[0].encode("utf-16-be"))
        return "{" + ",".join(_legacy_escape_str(k) + ":" + _legacy_encode(v) for k, v in items) + "}"
    raise TypeError(f"Unsupported type for canonical JSON: {type(value).__name__}")


def legacy_canonical_json_bytes(obj: Any) -> bytes:
    """Pre-RFC-8785 encoder bytes. ONLY for verifying receipts signed before
    the JCS-library cutover. New code MUST call :func:`canonical_json_bytes`.
    """

    return _legacy_encode(obj).encode("utf-8")


# ---------------------------------------------------------------------------
# Dual-encoder verification helper.
# ---------------------------------------------------------------------------


def verify_canonical_match(obj: Any, verifier: Any) -> bool:
    """Try the RFC 8785 encoder first; on failure, fall back to legacy bytes.

    *verifier* is any callable ``(canonical_bytes: bytes) -> bool`` that
    performs the actual cryptographic check. Returns ``True`` as soon as
    one encoding verifies; ``False`` if neither does.

    Used by both ``receipt_signer.verify_receipt`` (backend) and the
    verifier microservice to preserve compatibility with receipts signed
    before the JCS-library cutover.
    """

    new_bytes: bytes | None
    try:
        new_bytes = canonical_json_bytes(obj)
    except Exception:  # noqa: BLE001
        new_bytes = None
    if new_bytes is not None and verifier(new_bytes):
        return True

    try:
        old_bytes = legacy_canonical_json_bytes(obj)
    except Exception:  # noqa: BLE001
        return False
    if new_bytes is not None and old_bytes == new_bytes:
        # Avoid a redundant second verify call when both encoders agree.
        return False
    return verifier(old_bytes)
