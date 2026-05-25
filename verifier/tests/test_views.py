"""Tests for the verifier HTML views, badge endpoint, and content negotiation
wiring on the existing ``/verify/{id}`` route.
"""

from __future__ import annotations

import base64
import copy
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

RECEIPT_ID = "11111111-1111-1111-1111-111111111111"


def _backend_url() -> str:
    from app.main import settings

    base = settings.backend_base_url.rstrip("/")
    path = settings.backend_receipt_path.rstrip("/")
    return f"{base}{path}/{RECEIPT_ID}"


# ---------------------------------------------------------------------------
# Content negotiation on /verify/{id}
# ---------------------------------------------------------------------------


@respx.mock
def test_verify_default_returns_html(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    """Browsers send an explicit ``text/html`` Accept header — they should
    get the HTML view rendered."""

    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    browser_accept = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    )
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": browser_accept})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Verified" in resp.text
    assert RECEIPT_ID in resp.text


@respx.mock
def test_verify_html_accept_renders_template(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Verified" in resp.text
    # CSP + frame protection must be present on every HTML response.
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers["X-Frame-Options"] == "DENY"
    # OG meta tags for unfurls.
    assert 'property="og:title"' in resp.text
    assert 'property="og:image"' in resp.text


@respx.mock
def test_verify_invalid_signature_html_shows_invalid(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    tampered = copy.deepcopy(signed_envelope)
    raw = base64.b64decode(tampered["signature"])
    tampered["signature"] = base64.b64encode(bytes([raw[0] ^ 0x01]) + raw[1:]).decode(
        "ascii"
    )

    respx.get(_backend_url()).mock(return_value=httpx.Response(200, json=tampered))
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert "Invalid" in resp.text
    assert "tampered" in resp.text.lower() or "does not match" in resp.text.lower()


@respx.mock
def test_verify_not_found_html_friendly_page(configured_app: Any) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(404, json={"detail": "nope"})
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "text/html"})
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert "not found" in resp.text.lower()


@respx.mock
def test_verify_not_found_json_default_when_accept_json(
    configured_app: Any,
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(404, json={"detail": "nope"})
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "application/json"})
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "detail" in body


@respx.mock
def test_verify_jose_accept_returns_envelope(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"Accept": "application/jose+json"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/jose+json")
    body = resp.json()
    assert body["payload"]["receipt_id"] == RECEIPT_ID
    assert "signature" in body


# ---------------------------------------------------------------------------
# Forced format via extension routes
# ---------------------------------------------------------------------------


@respx.mock
def test_json_extension_forces_json_even_with_html_accept(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}.json", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["verified"] is True
    assert body["status"] == "verified"


@respx.mock
def test_html_extension_forces_html_even_with_json_accept(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}.html",
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Verified" in resp.text


# ---------------------------------------------------------------------------
# Badge endpoint
# ---------------------------------------------------------------------------


@respx.mock
def test_badge_verified_is_green_svg(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}/badge.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "verified" in resp.text
    assert "#2ea44f" in resp.text  # green
    # Required caching + CORS headers for an embeddable badge.
    assert "max-age=60" in resp.headers["cache-control"]
    assert "stale-while-revalidate" in resp.headers["cache-control"]
    assert resp.headers["etag"].startswith('"')
    assert resp.headers["access-control-allow-origin"] == "*"


@respx.mock
def test_badge_invalid_is_red_svg(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    tampered = copy.deepcopy(signed_envelope)
    raw = base64.b64decode(tampered["signature"])
    tampered["signature"] = base64.b64encode(bytes([raw[0] ^ 0x01]) + raw[1:]).decode(
        "ascii"
    )

    respx.get(_backend_url()).mock(return_value=httpx.Response(200, json=tampered))
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}/badge.svg")
    assert resp.status_code == 200
    assert "invalid" in resp.text
    assert "#cf222e" in resp.text  # red


# ---------------------------------------------------------------------------
# Static + JSON shape sanity
# ---------------------------------------------------------------------------


def test_static_assets_mounted(configured_app: Any) -> None:
    client = TestClient(configured_app)
    resp = client.get("/static/once-logo.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")


@respx.mock
def test_json_endpoint_back_compat_shape(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    body = resp.json()
    # Existing JSON contract preserved (verified, payload, public_key_pem,
    # signing_key_id) — Agent B6 / tooling relies on this.
    for key in ("verified", "payload", "public_key_pem", "signing_key_id"):
        assert key in body, f"missing {key}"
    assert body["verified"] is True


@respx.mock
def test_json_endpoint_fetches_public_key_by_signing_key_id(
    configured_app: Any,
    signed_envelope: dict[str, Any],
    public_key_pem: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import _PUBLIC_KEY_CACHE, settings

    _PUBLIC_KEY_CACHE.clear()
    monkeypatch.setattr(settings, "public_key_pem", "")
    monkeypatch.setattr(settings, "signing_key_id", "static-key")
    signed_envelope = {**signed_envelope, "signing_key_id": "rotated-key"}

    respx.get(_backend_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )
    respx.get("https://api.test.local/v1/keys/rotated-key").mock(
        return_value=httpx.Response(
            200,
            json={
                "key_id": "rotated-key",
                "algorithm": "Ed25519",
                "public_key_pem": public_key_pem,
                "created_at": "2026-05-25T00:00:00Z",
                "status": "active",
            },
        )
    )

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}", headers={"Accept": "application/json"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert body["signing_key_id"] == "rotated-key"
    assert body["public_key_pem"] == public_key_pem
