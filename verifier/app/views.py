"""HTML, badge, and forced-format view routes for the Once Verifier.

The canonical JSON verifier endpoint lives in :mod:`app.main`. This module
layers a human-facing experience on top: server-rendered HTML for browsers,
SVG status badges for embedding in other dashboards, and explicit
``.json`` / ``.html`` file-extension routes for tools that don't want to set
``Accept`` headers.

All routes delegate the actual cryptographic work to
``app.main.perform_verification`` so we only have one place that knows how to
talk to the backend and validate signatures.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app.og_card import render_og_svg

if TYPE_CHECKING:  # pragma: no cover
    pass


router = APIRouter()


_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)

_HTML_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def _verdict_for(result: Any) -> tuple[str, str, str]:
    """Return ``(verdict_key, headline, subtitle)`` for a verification result."""

    if result.status == "not_found":
        return (
            "not_found",
            "Receipt not found",
            (
                "We couldn't locate this receipt. It may have been deleted, "
                "expired, or the link may be malformed."
            ),
        )
    if result.status == "error":
        return (
            "error",
            "Verification error",
            result.error_detail
            or "An unexpected error occurred while verifying this receipt.",
        )
    if result.verified:
        payload = result.payload or {}
        supplier = payload.get("supplier_id") or payload.get("supplier") or "an unknown supplier"
        issued = (
            payload.get("submitted_at")
            or payload.get("issued_at")
            or "an earlier date"
        )
        return (
            "verified",
            "Verified",
            (
                f"This receipt was cryptographically signed by Once on {issued} "
                f"for supplier {supplier}."
            ),
        )
    return (
        "invalid",
        "Invalid signature",
        (
            "The signature does not match this payload. The receipt may have "
            "been tampered with, or the signing key is unknown to this "
            "verifier."
        ),
    )


def _render_html(
    request: Request,
    receipt_id: str,
    result: Any,
    status_code: int,
) -> HTMLResponse:
    from app.main import settings, templates

    verdict_key, headline, subtitle = _verdict_for(result)
    payload = result.payload or {}
    envelope = result.envelope or {}

    canonical_url = str(request.url).split("?", 1)[0]
    ctx = {
        "request": request,
        "receipt_id": receipt_id,
        "verdict": verdict_key,
        "headline": headline,
        "subtitle": subtitle,
        "payload": payload,
        "envelope": envelope,
        "signing_key_id": (
            envelope.get("signing_key_id") or settings.signing_key_id
        ),
        "public_key_pem": settings.public_key_pem or "",
        "canonical_url": canonical_url,
        "json_url": f"/verify/{receipt_id}.json",
        "badge_url": f"/verify/{receipt_id}/badge.svg",
        "og_image_url": f"/verify/{receipt_id}/og.svg",
        "service_name": settings.app_name,
    }
    response = templates.TemplateResponse(
        request, "verify.html", ctx, status_code=status_code
    )
    for k, v in _HTML_SECURITY_HEADERS.items():
        response.headers[k] = v
    return response


def _badge_svg(verdict_key: str) -> str:
    """Return shields.io-style SVG (88x31) for a verdict."""

    if verdict_key == "verified":
        right_label, right_color = "verified", "#2ea44f"
    elif verdict_key == "invalid":
        right_label, right_color = "invalid", "#cf222e"
    elif verdict_key == "not_found":
        right_label, right_color = "not found", "#bf8700"
    else:
        right_label, right_color = "error", "#6e7781"

    # Two-segment shields.io-style flat badge, 88x31. Hand-rolled to avoid a
    # runtime dep on a badge library. Text positions are tuned for 11px DejaVu.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="31" role="img" aria-label="once: {right_label}">
  <title>once: {right_label}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="120" height="31" rx="4" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="42" height="31" fill="#24292f"/>
    <rect x="42" width="78" height="31" fill="{right_color}"/>
    <rect width="120" height="31" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="21" y="20">once</text>
    <text x="81" y="20">{right_label}</text>
  </g>
</svg>"""


@router.get("/verify/{receipt_id}.json", include_in_schema=False)
async def verify_json(receipt_id: str) -> JSONResponse:
    from app.main import perform_verification

    result = await perform_verification(receipt_id)
    body: dict[str, Any] = {
        "receipt_id": receipt_id,
        "status": result.status,
        "verified": bool(result.verified),
    }
    if result.payload is not None:
        body["payload"] = result.payload
    if result.envelope:
        body["signing_key_id"] = (
            result.envelope.get("signing_key_id")
            or _settings_signing_key_id()
        )
    if result.error_detail:
        body["error"] = result.error_detail
    return JSONResponse(body, status_code=result.http_status)


def _settings_signing_key_id() -> str:
    from app.main import settings

    return settings.signing_key_id


@router.get("/verify/{receipt_id}.html", include_in_schema=False)
async def verify_html(request: Request, receipt_id: str) -> HTMLResponse:
    from app.main import perform_verification

    result = await perform_verification(receipt_id)
    return _render_html(request, receipt_id, result, result.http_status)


@router.get("/verify/{receipt_id}/badge.svg", include_in_schema=False)
async def verify_badge(receipt_id: str) -> Response:
    from app.main import perform_verification

    result = await perform_verification(receipt_id)
    verdict_key, _, _ = _verdict_for(result)
    svg = _badge_svg(verdict_key)
    etag = (
        '"'
        + hashlib.sha256(
            f"{receipt_id}:{verdict_key}".encode("utf-8")
        ).hexdigest()[:16]
        + '"'
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
            "ETag": etag,
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/verify/{receipt_id}/og.svg", include_in_schema=False)
async def verify_og_card(receipt_id: str) -> Response:
    """Branded per-receipt Open-Graph card for social unfurls.

    Renders a 1200x630 SVG with the verdict, supplier/portal/issued summary,
    and a short receipt glyph. Cached aggressively — the receipt itself is
    immutable, so the only reason content changes is the underlying receipt
    moving between verified/invalid (only possible if the signing key
    rotates), which is rare enough to tolerate a 5-minute stale window.
    """

    from app.main import perform_verification, settings

    result = await perform_verification(receipt_id)
    verdict_key, _, _ = _verdict_for(result)
    svg = render_og_svg(
        verdict=verdict_key,
        receipt_id=receipt_id,
        payload=result.payload,
        service_name=settings.app_name,
    )
    etag = (
        '"'
        + hashlib.sha256(
            f"og:{receipt_id}:{verdict_key}".encode("utf-8")
        ).hexdigest()[:16]
        + '"'
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=300, stale-while-revalidate=86400",
            "ETag": etag,
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = ["router"]
