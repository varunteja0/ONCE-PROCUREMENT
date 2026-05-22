"""Tests for verifier API-key auth + per-IP rate limiting middleware.

Phase L6.1 \u2014 monetization MVP. The middleware forwards plaintext keys to
the backend's ``/v1/internal/verifier-keys/charge`` endpoint and translates
the result. We mock that endpoint with ``respx``.
"""

from __future__ import annotations

import copy
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient


RECEIPT_ID = "11111111-1111-1111-1111-111111111111"
CHARGE_URL = "https://api.test.local/v1/internal/verifier-keys/charge"


def _receipt_url() -> str:
    return f"https://api.test.local/v1/public/receipts/{RECEIPT_ID}"


@pytest.fixture
def auth_app(
    configured_app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    from app.main import settings as verifier_settings

    monkeypatch.setattr(
        verifier_settings,
        "backend_internal_token",
        "test-backend-internal-token-do-not-log",
    )
    return configured_app


@respx.mock
def test_valid_api_key_passes_through(
    auth_app: Any, signed_envelope: dict[str, Any]
) -> None:
    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "api_key_id": "key-abc",
                "tenant_id": "tenant-xyz",
                "monthly_call_cap": 10000,
                "current_period_count": 1,
                "period_month": "2026-05",
            },
        )
    )
    respx.get(_receipt_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )

    client = TestClient(auth_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_anything"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is True


@respx.mock
def test_invalid_api_key_returns_401(auth_app: Any) -> None:
    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(
            401, json={"detail": {"code": "invalid_api_key"}}
        )
    )

    client = TestClient(auth_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_garbage"},
    )

    assert resp.status_code == 401
    assert resp.json() == {"detail": {"code": "invalid_api_key"}}


@respx.mock
def test_quota_exceeded_returns_402_with_backend_body(auth_app: Any) -> None:
    backend_402 = {
        "detail": {
            "code": "quota_exceeded",
            "api_key_id": "key-abc",
            "monthly_call_cap": 10,
            "current_period_count": 11,
            "period_month": "2026-05",
        }
    }
    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(402, json=backend_402)
    )

    client = TestClient(auth_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_anything"},
    )

    assert resp.status_code == 402
    assert resp.json() == backend_402


@respx.mock
def test_charge_backend_unreachable_returns_503(auth_app: Any) -> None:
    respx.post(CHARGE_URL).mock(side_effect=httpx.ConnectError("boom"))

    client = TestClient(auth_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_anything"},
    )

    assert resp.status_code == 503


def test_missing_backend_internal_token_returns_503(
    configured_app: Any,
) -> None:
    # No monkeypatch of backend_internal_token \u2014 it stays empty by default.
    client = TestClient(configured_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_anything"},
    )
    assert resp.status_code == 503


@respx.mock
def test_unauth_request_consumes_rate_limit(
    configured_app: Any,
    monkeypatch: pytest.MonkeyPatch,
    signed_envelope: dict[str, Any],
) -> None:
    from app.main import settings as verifier_settings

    monkeypatch.setattr(verifier_settings, "unauth_rate_limit", "2/minute")

    respx.get(_receipt_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )

    client = TestClient(configured_app)
    r1 = client.get(f"/verify/{RECEIPT_ID}")
    r2 = client.get(f"/verify/{RECEIPT_ID}")
    r3 = client.get(f"/verify/{RECEIPT_ID}")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.headers.get("Retry-After") == "60"


@respx.mock
def test_api_key_requests_bypass_rate_limit(
    auth_app: Any,
    monkeypatch: pytest.MonkeyPatch,
    signed_envelope: dict[str, Any],
) -> None:
    from app.main import settings as verifier_settings

    monkeypatch.setattr(verifier_settings, "unauth_rate_limit", "1/minute")

    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "api_key_id": "key-abc",
                "tenant_id": "tenant-xyz",
                "monthly_call_cap": None,
                "current_period_count": 1,
                "period_month": "2026-05",
            },
        )
    )
    respx.get(_receipt_url()).mock(
        return_value=httpx.Response(200, json=signed_envelope)
    )

    client = TestClient(auth_app)
    headers = {"X-Verify-API-Key": "vk_live_anything"}
    for _ in range(3):
        resp = client.get(f"/verify/{RECEIPT_ID}", headers=headers)
        assert resp.status_code == 200, resp.text


def test_health_endpoint_is_not_rate_limited(
    configured_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import settings as verifier_settings

    monkeypatch.setattr(verifier_settings, "unauth_rate_limit", "1/minute")

    client = TestClient(configured_app)
    for _ in range(5):
        assert client.get("/health").status_code == 200
        assert client.get("/healthz").status_code == 200


@respx.mock
def test_tampered_payload_still_returns_response_when_authed(
    auth_app: Any, signed_envelope: dict[str, Any]
) -> None:
    """Sanity: auth path doesn't interfere with verification verdict."""

    tampered = copy.deepcopy(signed_envelope)
    tampered["payload"]["supplier_id"] = "ffffffff-ffff-ffff-ffff-ffffffffffff"

    respx.post(CHARGE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "api_key_id": "key-abc",
                "tenant_id": "tenant-xyz",
                "monthly_call_cap": 10,
                "current_period_count": 5,
                "period_month": "2026-05",
            },
        )
    )
    respx.get(_receipt_url()).mock(
        return_value=httpx.Response(200, json=tampered)
    )

    client = TestClient(auth_app)
    resp = client.get(
        f"/verify/{RECEIPT_ID}",
        headers={"X-Verify-API-Key": "vk_live_anything"},
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is False
