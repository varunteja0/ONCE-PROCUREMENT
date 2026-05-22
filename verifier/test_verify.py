"""Verifier signature-verification tests.

Uses ``respx`` to intercept ``httpx.AsyncClient`` calls to the backend's
public receipt endpoint and assert that the verifier correctly accepts a
valid Ed25519 signature and rejects a tampered one.
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


def _backend_url(configured_app: Any) -> str:
    # Mirror the URL construction in app/main.py::_fetch_receipt.
    from app.main import settings

    base = settings.backend_base_url.rstrip("/")
    path = settings.backend_receipt_path.rstrip("/")
    return f"{base}{path}/{RECEIPT_ID}"


@respx.mock
def test_verify_valid_signature(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    url = _backend_url(configured_app)
    respx.get(url).mock(return_value=httpx.Response(200, json=signed_envelope))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["payload"]["receipt_id"] == RECEIPT_ID
    assert body["signing_key_id"] == "test-key"


@respx.mock
def test_verify_bad_signature(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    tampered = copy.deepcopy(signed_envelope)
    raw = base64.b64decode(tampered["signature"])
    # Flip a single byte to invalidate the signature without changing length.
    flipped = bytes([raw[0] ^ 0x01]) + raw[1:]
    tampered["signature"] = base64.b64encode(flipped).decode("ascii")

    url = _backend_url(configured_app)
    respx.get(url).mock(return_value=httpx.Response(200, json=tampered))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False


@respx.mock
def test_verify_tampered_payload_fails(
    configured_app: Any, signed_envelope: dict[str, Any]
) -> None:
    tampered = copy.deepcopy(signed_envelope)
    tampered["payload"]["supplier_id"] = "99999999-9999-9999-9999-999999999999"

    url = _backend_url(configured_app)
    respx.get(url).mock(return_value=httpx.Response(200, json=tampered))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")

    assert resp.status_code == 200
    assert resp.json()["verified"] is False


@respx.mock
def test_verify_receipt_not_found(configured_app: Any) -> None:
    url = _backend_url(configured_app)
    respx.get(url).mock(return_value=httpx.Response(404, json={"detail": "nope"}))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")
    assert resp.status_code == 404


@respx.mock
def test_verify_backend_unreachable(configured_app: Any) -> None:
    url = _backend_url(configured_app)
    respx.get(url).mock(side_effect=httpx.ConnectError("boom"))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")
    assert resp.status_code == 404


@respx.mock
def test_verify_envelope_missing_fields(configured_app: Any) -> None:
    url = _backend_url(configured_app)
    respx.get(url).mock(return_value=httpx.Response(200, json={"payload": {}}))

    client = TestClient(configured_app)
    resp = client.get(f"/verify/{RECEIPT_ID}")
    assert resp.status_code == 422


def test_canonical_json_matches_backend_format() -> None:
    """Sanity check: our canonical encoder produces the RFC8785 form expected."""

    from app.canonical import canonical_json_bytes

    # Keys must be sorted by UTF-16-BE; nested order preserved; no whitespace.
    encoded = canonical_json_bytes({"b": 1, "a": [3, 2, 1], "c": {"y": True, "x": None}})
    assert encoded == b'{"a":[3,2,1],"b":1,"c":{"x":null,"y":true}}'
