"""HTTP Accept-header content negotiation for the Once Verifier.

Parses ``Accept`` headers with q-values per RFC 7231 §5.3 and returns one of
the three formats the verifier knows how to emit: HTML for browsers, JSON for
tooling, and the raw signed JOSE envelope for advanced clients.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Request

Format = Literal["html", "json", "jose"]

_MEDIA_TYPE_TO_FORMAT: dict[str, Format] = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/json": "json",
    "application/jose+json": "jose",
    "application/jose": "jose",
}

# What we return when the client sends only a wildcard or no Accept at all.
_WILDCARD_FORMATS: tuple[Format, ...] = ("html", "json", "jose")


def _parse_accept(header: str) -> list[tuple[str, float, int]]:
    """Parse an Accept header into ``(media_type, q, original_index)`` tuples.

    Invalid q-values fall back to ``1.0`` (the RFC default). ``original_index``
    is used as a stable tiebreaker so the leftmost entry wins when q-values
    are equal — matching how every major browser actually behaves.
    """

    items: list[tuple[str, float, int]] = []
    for idx, raw in enumerate(header.split(",")):
        part = raw.strip()
        if not part:
            continue
        bits = [b.strip() for b in part.split(";") if b.strip()]
        if not bits:
            continue
        media_type = bits[0].lower()
        q = 1.0
        for param in bits[1:]:
            if param.lower().startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 1.0
                break
        if q < 0 or q > 1:
            q = 1.0
        items.append((media_type, q, idx))
    return items


def negotiate(request: Request, default: Format = "html") -> Format:
    """Pick the best response format for *request*.

    Resolution order:
        1. If the path ends in ``.json`` / ``.html`` the caller has already
           routed it; this function is not consulted.
        2. Parse the ``Accept`` header. Walk acceptable media types in
           descending q-value order and return the first known format.
        3. Wildcards (``*/*``, ``application/*``) resolve to *default*.
        4. Missing/empty header → *default*.
    """

    header = request.headers.get("accept", "").strip()
    if not header:
        return default

    parsed = _parse_accept(header)
    if not parsed:
        return default

    # Sort by q desc, then original index asc (stable tiebreak).
    parsed.sort(key=lambda t: (-t[1], t[2]))

    for media_type, q, _ in parsed:
        if q <= 0:
            continue
        fmt = _MEDIA_TYPE_TO_FORMAT.get(media_type)
        if fmt is not None:
            return fmt
        if media_type in {"*/*", "application/*", "text/*"}:
            # Honor the wildcard but prefer the default if it's compatible.
            if media_type == "text/*":
                return "html"
            if media_type == "application/*":
                return "json"
            return default

    return default


__all__ = ["negotiate", "Format"]
