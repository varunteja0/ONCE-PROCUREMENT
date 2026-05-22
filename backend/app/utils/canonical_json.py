from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Final

__all__ = ["canonical_json_bytes", "canonical_json_str", "payload_sha256"]


_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r'[\\"\x00-\x1f]')
_ESCAPE_MAP: Final[dict[str, str]] = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _escape_str(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        char = match.group(0)
        mapped = _ESCAPE_MAP.get(char)
        if mapped is not None:
            return mapped
        return f"\\u{ord(char):04x}"

    return '"' + _ESCAPE_RE.sub(replace, value) + '"'


def _format_number(value: int | float) -> str:
    if isinstance(value, bool):  # pragma: no cover - handled separately
        raise TypeError("bool should not reach _format_number")
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


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _format_number(value)
    if isinstance(value, str):
        return _escape_str(value)
    if isinstance(value, list | tuple):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        items: list[tuple[str, Any]] = []
        for key, val in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Canonical JSON object keys must be strings, got {type(key).__name__}"
                )
            items.append((key, val))
        items.sort(key=lambda kv: kv[0].encode("utf-16-be"))
        return "{" + ",".join(_escape_str(k) + ":" + _encode(v) for k, v in items) + "}"
    raise TypeError(f"Unsupported type for canonical JSON: {type(value).__name__}")


def canonical_json_str(obj: Any) -> str:
    """Return RFC8785-style canonical JSON string for *obj*."""

    return _encode(obj)


def canonical_json_bytes(obj: Any) -> bytes:
    """Return RFC8785-style canonical JSON UTF-8 bytes for *obj*."""

    return _encode(obj).encode("utf-8")


def payload_sha256(obj: Any) -> str:
    """Return hex SHA-256 digest of the canonical JSON encoding of *obj*."""

    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
