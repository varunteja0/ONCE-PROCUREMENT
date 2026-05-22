"""Shared pytest fixtures for the Once Verifier service.

Generates a fresh Ed25519 keypair per test session, signs a canonical receipt
envelope, and exposes the verifier FastAPI ``app`` with the public key wired
into ``settings``.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.canonical import canonical_json_bytes
from app.main import app as fastapi_app
from app.main import settings as verifier_settings


@pytest.fixture(scope="session")
def ed25519_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="session")
def public_key_pem(ed25519_keypair: tuple[Ed25519PrivateKey, Ed25519PublicKey]) -> str:
    _, public_key = ed25519_keypair
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    return {
        "receipt_id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "supplier_id": "33333333-3333-3333-3333-333333333333",
        "portal": "amtrust",
        "submission_id": "44444444-4444-4444-4444-444444444444",
        "submitted_at": "2025-01-15T12:34:56Z",
        "payload_hash": "0" * 64,
        "tos_version_hash": "1" * 64,
        "consent_record_id": "55555555-5555-5555-5555-555555555555",
    }


@pytest.fixture
def signed_envelope(
    ed25519_keypair: tuple[Ed25519PrivateKey, Ed25519PublicKey],
    sample_payload: dict[str, Any],
) -> dict[str, Any]:
    private_key, _ = ed25519_keypair
    signed_bytes = canonical_json_bytes(sample_payload)
    signature = private_key.sign(signed_bytes)
    return {
        "payload": sample_payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signing_key_id": "test-key",
    }


@pytest.fixture
def configured_app(
    monkeypatch: pytest.MonkeyPatch, public_key_pem: str
) -> Any:
    monkeypatch.setattr(verifier_settings, "public_key_pem", public_key_pem)
    monkeypatch.setattr(
        verifier_settings, "backend_base_url", "https://api.test.local"
    )
    monkeypatch.setattr(
        verifier_settings, "backend_receipt_path", "/v1/public/receipts/"
    )
    monkeypatch.setattr(verifier_settings, "signing_key_id", "test-key")
    return fastapi_app


@pytest.fixture(autouse=True)
def _reset_rate_limit_storage() -> None:
    """Each test gets a fresh in-process rate-limit window.

    The verifier's per-IP rate limiter holds state in a process-local
    ``MemoryStorage`` (``app/api_key.py``); without this reset, tests that
    exercise ``/verify/*`` would accumulate hits across tests and
    intermittently 429.
    """

    from app.api_key import reset_rate_limit_storage

    reset_rate_limit_storage()

