"""Stripe SDK adapter — lazy-init + mock-mode for hermetic tests.

The real :mod:`stripe` package is imported lazily so the app can boot and
tests can run without it installed. When ``STRIPE_MOCK_MODE`` is true (the
default in dev/tests) we return a deterministic in-memory fake that mirrors
the subset of the Stripe API the rest of the codebase touches:

* ``checkout.Session.create``
* ``billingPortal.Session.create``
* ``Webhook.construct_event`` (HMAC-SHA256 over ``"{ts}.{body}"``)

The fake is enough to drive every API path under test without ever hitting
``api.stripe.com``. In live mode the wrapper delegates to the real SDK so
behavior is identical.

This module is intentionally the **only** place the codebase imports
``stripe``; ``billing_service`` and ``billing_webhooks`` consume the
:func:`get_stripe_client` interface.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "StripeClient",
    "StripeSignatureError",
    "get_stripe_client",
    "reset_stripe_client_cache",
    "build_mock_signature_header",
]


_logger = get_logger(__name__)


class StripeSignatureError(Exception):
    """Raised when webhook signature verification fails."""


class StripeClient(Protocol):
    """Surface area billing_* services depend on."""

    mock_mode: bool

    def create_checkout_session(
        self,
        *,
        customer_email: str | None,
        customer_id: str | None,
        client_reference_id: str,
        line_items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def create_billing_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> dict[str, Any]:
        ...

    def construct_event(
        self, *, payload: bytes, sig_header: str, secret: str
    ) -> dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------


def _now_ts() -> int:
    return int(time.time())


def build_mock_signature_header(
    *, payload: bytes, secret: str, timestamp: int | None = None
) -> str:
    """Generate a Stripe-compatible ``t=<ts>,v1=<sig>`` header for tests."""

    ts = timestamp if timestamp is not None else _now_ts()
    signed_payload = f"{ts}.".encode() + payload
    digest = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={digest}"


def _verify_mock_signature(
    *, payload: bytes, sig_header: str, secret: str, tolerance_sec: int = 300
) -> None:
    if not sig_header:
        raise StripeSignatureError("missing signature header")
    parts = {}
    for chunk in sig_header.split(","):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        parts.setdefault(k.strip(), []).append(v.strip())
    ts_raw = parts.get("t", [None])[0]
    sigs = parts.get("v1", [])
    if not ts_raw or not sigs:
        raise StripeSignatureError("malformed signature header")
    try:
        ts = int(ts_raw)
    except ValueError as exc:
        raise StripeSignatureError("invalid timestamp") from exc
    if abs(_now_ts() - ts) > tolerance_sec:
        raise StripeSignatureError("timestamp outside tolerance")
    signed_payload = f"{ts}.".encode() + payload
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in sigs):
        raise StripeSignatureError("signature mismatch")


@dataclass
class _MockStripeClient:
    """In-memory Stripe SDK substitute. Deterministic for tests."""

    mock_mode: bool = True
    _sessions: list[dict[str, Any]] = field(default_factory=list)
    _portal_sessions: list[dict[str, Any]] = field(default_factory=list)

    def create_checkout_session(
        self,
        *,
        customer_email: str | None,
        customer_id: str | None,
        client_reference_id: str,
        line_items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_id = f"cs_test_{secrets.token_hex(12)}"
        session = {
            "id": session_id,
            "url": (
                f"https://checkout.stripe.com/c/pay/{session_id}"
                f"#fid={secrets.token_hex(8)}"
            ),
            "customer": customer_id,
            "customer_email": customer_email,
            "client_reference_id": client_reference_id,
            "line_items": line_items,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
            "mode": "subscription",
            "status": "open",
        }
        self._sessions.append(session)
        return session

    def create_billing_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> dict[str, Any]:
        session = {
            "id": f"bps_test_{secrets.token_hex(10)}",
            "url": (
                f"https://billing.stripe.com/p/session/test_{secrets.token_hex(10)}"
            ),
            "customer": customer_id,
            "return_url": return_url,
        }
        self._portal_sessions.append(session)
        return session

    def construct_event(
        self, *, payload: bytes, sig_header: str, secret: str
    ) -> dict[str, Any]:
        _verify_mock_signature(payload=payload, sig_header=sig_header, secret=secret)
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StripeSignatureError("payload is not valid JSON") from exc
        if not isinstance(parsed, dict) or "id" not in parsed or "type" not in parsed:
            raise StripeSignatureError("payload missing required fields")
        return parsed


# ---------------------------------------------------------------------------
# Live implementation (thin wrapper around the real SDK)
# ---------------------------------------------------------------------------


@dataclass
class _LiveStripeClient:
    mock_mode: bool = False
    api_key: str = ""

    def _stripe(self):  # type: ignore[no-untyped-def]
        import stripe  # type: ignore[import-not-found]

        stripe.api_key = self.api_key
        return stripe

    def create_checkout_session(
        self,
        *,
        customer_email: str | None,
        customer_id: str | None,
        client_reference_id: str,
        line_items: list[dict[str, Any]],
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stripe = self._stripe()
        kwargs: dict[str, Any] = {
            "mode": "subscription",
            "line_items": line_items,
            "client_reference_id": client_reference_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
            "allow_promotion_codes": True,
        }
        if customer_id:
            kwargs["customer"] = customer_id
        elif customer_email:
            kwargs["customer_email"] = customer_email
        session = stripe.checkout.Session.create(**kwargs)
        return dict(session)

    def create_billing_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> dict[str, Any]:
        stripe = self._stripe()
        session = stripe.billing_portal.Session.create(
            customer=customer_id, return_url=return_url
        )
        return dict(session)

    def construct_event(
        self, *, payload: bytes, sig_header: str, secret: str
    ) -> dict[str, Any]:
        stripe = self._stripe()
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except Exception as exc:  # pragma: no cover - live path
            raise StripeSignatureError(str(exc)) from exc
        return dict(event)


# ---------------------------------------------------------------------------
# Cached accessor
# ---------------------------------------------------------------------------


_cached_client: StripeClient | None = None


def get_stripe_client() -> StripeClient:
    """Return the process-wide Stripe client (mock or live)."""

    global _cached_client
    if _cached_client is not None:
        return _cached_client

    if settings.stripe_mock_mode or not settings.stripe_secret_key:
        if not settings.stripe_mock_mode:
            _logger.warning(
                "stripe_mock_fallback",
                reason="STRIPE_SECRET_KEY not configured; using mock client",
            )
        _cached_client = _MockStripeClient()
    else:
        _cached_client = _LiveStripeClient(api_key=settings.stripe_secret_key)
    return _cached_client


def reset_stripe_client_cache() -> None:
    """Drop the cached client (test helper, e.g. after env mutation)."""

    global _cached_client
    _cached_client = None
