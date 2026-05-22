"""ETag computation + conditional-request helpers.

We support two flavors of entity tag:

* **Weak ETags** (``W/"<hex>"``) derived from a SHA-256 of the serialized
  response body. Used by the conditional-request middleware to short-circuit
  GETs that produce identical bytes.
* **Strong ETags** (``"<hex>"``) derived from a deterministic model
  fingerprint (e.g. row PK + ``updated_at``). Used by routes that want
  precise concurrency control via ``If-Match`` on mutating requests.

Both forms are wrapped in double-quotes per RFC 7232.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from fastapi import HTTPException, Request

__all__ = [
    "compute_weak_etag",
    "compute_strong_etag",
    "etag_matches",
    "if_none_match_hits",
    "check_if_match",
]


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_weak_etag(body: bytes) -> str:
    """Weak ETag for a response body. Format: ``W/"<sha256-hex>"``."""

    digest = _hash(body if isinstance(body, bytes | bytearray) else bytes(body))
    return f'W/"{digest}"'


def compute_strong_etag(*parts: Any) -> str:
    """Strong ETag from arbitrary identifying parts (joined with ``\\x1f``)."""

    joined = "\x1f".join("" if p is None else str(p) for p in parts).encode("utf-8")
    return f'"{_hash(joined)}"'


def _normalize_token(token: str) -> str:
    token = token.strip()
    if token.startswith("W/"):
        token = token[2:].strip()
    return token


def _parse_if_header(value: str) -> Iterable[str]:
    # If-Match / If-None-Match are comma-separated entity-tag lists.
    for raw in value.split(","):
        candidate = _normalize_token(raw)
        if candidate:
            yield candidate


def etag_matches(presented: str, current: str) -> bool:
    """Weak comparison per RFC 7232 § 2.3.2."""

    if presented == "*":
        return True
    return _normalize_token(presented) == _normalize_token(current)


def if_none_match_hits(request: Request, current_etag: str) -> bool:
    """``True`` iff any of the client's If-None-Match tags matches."""

    raw = request.headers.get("If-None-Match")
    if not raw:
        return False
    if "*" in raw:
        return True
    return any(etag_matches(tok, current_etag) for tok in _parse_if_header(raw))


def check_if_match(request: Request, current_etag: str | None) -> None:
    """Enforce ``If-Match`` for state-changing requests.

    Routes performing optimistic concurrency control should call this with
    the resource's current ETag before applying mutations. Behavior:

    * header absent → no-op (clients without ETag awareness are tolerated);
    * header present + matches → no-op;
    * header present + mismatch → raises 412 ``precondition_failed``;
    * header is ``*`` + resource exists → no-op (matches anything);
    * header is ``*`` + resource missing → raises 412 (RFC 9110 § 13.1.1).
    """

    raw = request.headers.get("If-Match")
    if not raw:
        return
    if "*" in raw:
        if current_etag is None:
            raise HTTPException(status_code=412, detail="precondition_failed")
        return
    if current_etag is None:
        raise HTTPException(status_code=412, detail="precondition_failed")
    for token in _parse_if_header(raw):
        if etag_matches(token, current_etag):
            return
    raise HTTPException(status_code=412, detail="precondition_failed")
