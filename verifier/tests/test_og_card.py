"""Tests for the verifier per-receipt Open-Graph card endpoint."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.og_card import render_og_svg


RECEIPT_ID = "11111111-1111-1111-1111-111111111111"


def _backend_url() -> str:
    from app.main import settings

    base = settings.backend_base_url.rstrip("/")
    path = settings.backend_receipt_path.rstrip("/")
    return f"{base}{path}/{RECEIPT_ID}"


# ---------------------------------------------------------------------------
# Pure renderer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict,expected_label",
    [
        ("verified", "Verified"),
        ("invalid", "Invalid signature"),
        ("not_found", "Receipt not found"),
        ("error", "Verification error"),
    ],
)
def test_render_og_svg_contains_label_for_each_verdict(
    verdict: str, expected_label: str
) -> None:
    svg = render_og_svg(verdict=verdict, receipt_id=RECEIPT_ID)  # type: ignore[arg-type]
    assert svg.startswith("<svg")
    assert "1200" in svg and "630" in svg
    assert expected_label in svg


def test_render_og_svg_includes_payload_fields_when_present() -> None:
    payload = {
        "supplier_id": "acme-co",
        "portal": "amtrust",
        "submitted_at": "2026-01-15T12:34:56Z",
    }
    svg = render_og_svg(
        verdict="verified", receipt_id=RECEIPT_ID, payload=payload
    )
    assert "acme-co" in svg
    assert "amtrust" in svg
    assert "2026-01-15T12:34:56Z" in svg
    assert "SUPPLIER" in svg


def test_render_og_svg_escapes_user_controlled_input() -> None:
    payload = {"supplier_id": "<script>alert(1)</script>"}
    svg = render_og_svg(
        verdict="verified", receipt_id=RECEIPT_ID, payload=payload
    )
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_render_og_svg_truncates_long_supplier_names() -> None:
    long_name = "x" * 200
    svg = render_og_svg(
        verdict="verified",
        receipt_id=RECEIPT_ID,
        payload={"supplier_id": long_name},
    )
    assert "x" * 200 not in svg
    assert "…" in svg


def test_render_og_svg_handles_unknown_verdict_gracefully() -> None:
    svg = render_og_svg(verdict="something_weird", receipt_id=RECEIPT_ID)  # type: ignore[arg-type]
    assert svg.startswith("<svg")
    assert "Verification error" in svg


# ---------------------------------------------------------------------------
# HTTP route
# ---------------------------------------------------------------------------


@respx.mock
def test_og_endpoint_returns_svg_for_verified(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}/og.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    body = resp.text
    assert body.startswith("<svg")
    assert "Verified" in body
    assert signed_envelope["payload"]["supplier_id"] in body


@respx.mock
def test_og_endpoint_sets_cache_and_etag(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}/og.svg")
    assert resp.status_code == 200
    assert "Cache-Control" in resp.headers
    assert "max-age" in resp.headers["Cache-Control"]
    assert "ETag" in resp.headers
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


@respx.mock
def test_og_endpoint_etag_stable_across_calls(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    r1 = client.get(f"/verify/{RECEIPT_ID}/og.svg")
    r2 = client.get(f"/verify/{RECEIPT_ID}/og.svg")
    assert r1.headers["ETag"] == r2.headers["ETag"]


@respx.mock
def test_og_endpoint_handles_not_found(configured_app: Any) -> None:
    respx.get(_backend_url()).mock(return_value=httpx.Response(404))
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}/og.svg")
    # Always 200 — the card itself renders the not_found state so social
    # unfurls show the verdict instead of breaking with an HTTP error.
    assert resp.status_code == 200
    assert "Receipt not found" in resp.text


@respx.mock
def test_html_view_references_dynamic_og_image(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}.html",
        headers={"Accept": "text/html"},
    )
    assert resp.status_code == 200
    assert f"/verify/{RECEIPT_ID}/og.svg" in resp.text
    assert 'property="og:image"' in resp.text
    assert 'name="twitter:image"' in resp.text
