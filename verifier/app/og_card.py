"""Branded Open-Graph card generator for the Once Verifier.

Renders a 1200x630 SVG card per receipt with the verification verdict,
supplier identity, and a short receipt-id glyph. The card is intended to be
referenced from the ``<meta property="og:image">`` tag on the verify HTML
page, giving Twitter/Discord/LinkedIn rich unfurls that show the verdict
without the consumer needing to click through.

Pure-stdlib implementation — no Pillow, no headless Chromium, no fonts to
ship. SVG is rendered server-side as a string and served with a long cache
``ETag`` so the same receipt always yields the same byte stream.

Design constraints:

* 1200x630 (standard og:image aspect ratio, used by Twitter / Slack / Discord).
* All text uses the platform default sans-serif so we don't need to bundle
  a font file inside the container image.
* Everything is in a single ``<svg>`` element — no external image refs,
  no JS, no remote fonts. Self-contained so it works inside email
  preview tools and image proxies.
* HTML-escapes every user-controlled string before composition.

Module layout:

* :func:`render_og_svg` is the single public entrypoint. Given a verdict
  and an optional payload dict, returns the SVG document as a ``str``.
* All helpers are private. The module is intentionally tiny — adding
  features means adding test cases first.
"""

from __future__ import annotations

import html
from typing import Any, Literal

Verdict = Literal["verified", "invalid", "not_found", "error"]


_PALETTE: dict[Verdict, dict[str, str]] = {
    "verified": {
        "accent": "#10b981",
        "accent_dark": "#047857",
        "icon": "✓",
        "label": "Verified",
        "subtitle": "Signed by Once · Ed25519 · RFC 8785",
    },
    "invalid": {
        "accent": "#ef4444",
        "accent_dark": "#b91c1c",
        "icon": "✗",
        "label": "Invalid signature",
        "subtitle": "Signature does not match payload",
    },
    "not_found": {
        "accent": "#f59e0b",
        "accent_dark": "#b45309",
        "icon": "?",
        "label": "Receipt not found",
        "subtitle": "No record of this receipt id",
    },
    "error": {
        "accent": "#64748b",
        "accent_dark": "#334155",
        "icon": "!",
        "label": "Verification error",
        "subtitle": "Could not complete verification",
    },
}


def _short_receipt(receipt_id: str) -> str:
    """Return a friendly short form for the receipt id.

    For UUID-shaped ids we surface the first segment + last segment so the
    glyph reads "11111111…111111111111" without dominating the card. For
    non-UUID strings we just truncate to 24 chars with a middle ellipsis.
    """

    rid = receipt_id.strip()
    if len(rid) <= 16:
        return rid
    return f"{rid[:8]}…{rid[-8:]}"


def _line(text: str, max_chars: int) -> str:
    """Naive single-line truncation. SVG ``<text>`` has no wrap support so
    callers chunk multi-line copy into separate elements; this helper just
    keeps a single value from blowing out the card width."""

    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def render_og_svg(
    verdict: Verdict,
    receipt_id: str,
    payload: dict[str, Any] | None = None,
    *,
    service_name: str = "Once",
    tagline: str = "Receipt verification",
    site_url: str = "getonce.com",
) -> str:
    """Render the per-receipt OG card as a self-contained SVG string.

    Args:
        verdict: One of ``verified``, ``invalid``, ``not_found``, ``error``.
        receipt_id: The opaque receipt identifier (UUID or otherwise).
        payload: Optional decoded receipt payload — we surface ``supplier_id``
            / ``portal`` / ``submitted_at`` if present. Missing fields are
            silently skipped.
        service_name / tagline / site_url: Branding hooks. Defaults match
            the public Once verifier deployment but tests can override.

    Returns:
        A complete ``<svg xmlns="...">…</svg>`` document.
    """

    palette = _PALETTE.get(verdict, _PALETTE["error"])
    payload = payload or {}

    supplier = payload.get("supplier_id") or payload.get("supplier") or ""
    portal = payload.get("portal") or ""
    issued = (
        payload.get("submitted_at")
        or payload.get("issued_at")
        or ""
    )

    e_service = html.escape(service_name)
    e_tagline = html.escape(tagline)
    e_site = html.escape(site_url)
    e_label = html.escape(palette["label"])
    e_subtitle = html.escape(palette["subtitle"])
    e_icon = html.escape(palette["icon"])
    e_receipt = html.escape(_short_receipt(receipt_id))

    rows: list[str] = []
    if supplier:
        rows.append(("Supplier", _line(str(supplier), 38)))
    if portal:
        rows.append(("Portal", _line(str(portal), 38)))
    if issued:
        rows.append(("Issued", _line(str(issued), 38)))
    rows.append(("Receipt", _short_receipt(receipt_id)))

    row_svg_parts: list[str] = []
    base_y = 380
    line_height = 54
    for i, (label, value) in enumerate(rows):
        y = base_y + i * line_height
        row_svg_parts.append(
            f'<text x="80" y="{y}" font-size="22" fill="#94a3b8" '
            f'font-family="ui-sans-serif,system-ui,sans-serif">'
            f"{html.escape(label).upper()}</text>"
        )
        row_svg_parts.append(
            f'<text x="240" y="{y}" font-size="26" fill="#e2e8f0" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" '
            f'font-weight="500">'
            f"{html.escape(value)}</text>"
        )

    rows_svg = "\n  ".join(row_svg_parts)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630" role="img" aria-label="{e_service} · {e_label}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0f172a"/>
      <stop offset="1" stop-color="#020617"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{palette['accent']}"/>
      <stop offset="1" stop-color="{palette['accent_dark']}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="0" y="0" width="12" height="630" fill="url(#accent)"/>

  <g font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif">
    <text x="80" y="100" font-size="28" fill="#94a3b8" letter-spacing="3">{e_service.upper()}</text>
    <text x="80" y="138" font-size="22" fill="#64748b">{e_tagline}</text>

    <circle cx="1040" cy="120" r="60" fill="{palette['accent']}" opacity="0.15"/>
    <circle cx="1040" cy="120" r="44" fill="{palette['accent']}"/>
    <text x="1040" y="142" font-size="56" font-weight="700" fill="#ffffff" text-anchor="middle">{e_icon}</text>

    <text x="80" y="280" font-size="72" font-weight="700" fill="#f8fafc">{e_label}</text>
    <text x="80" y="324" font-size="26" fill="#94a3b8">{e_subtitle}</text>

    {rows_svg}

    <line x1="80" y1="540" x2="1120" y2="540" stroke="#1e293b" stroke-width="1"/>
    <text x="80" y="585" font-size="22" fill="#64748b">Verify at</text>
    <text x="170" y="585" font-size="22" fill="#e2e8f0" font-weight="600">{e_site}</text>
  </g>
</svg>"""


__all__ = ["render_og_svg", "Verdict"]
