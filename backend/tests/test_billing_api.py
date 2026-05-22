"""Billing API endpoint tests."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.webhooks import stripe_webhook_router
from app.models.billing import (
    BillingPriceConfig,
    SubscriptionStatus,
)
from app.services import billing_service
from app.services.stripe_client import (
    build_mock_signature_header,
    reset_stripe_client_cache,
)
from tests.conftest import register_user

pytestmark = pytest.mark.asyncio


WEBHOOK_SECRET = "whsec_test_api"


@pytest.fixture(autouse=True)
def _stripe_test_env(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.stripe_mock_mode", True, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.stripe_webhook_secret",
        WEBHOOK_SECRET,
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.stripe_price_setup_id",
        "price_setup_env",
        raising=False,
    )
    monkeypatch.setattr(
        "app.config.settings.stripe_price_monthly_id",
        "price_monthly_env",
        raising=False,
    )
    reset_stripe_client_cache()
    yield
    reset_stripe_client_cache()


@pytest.fixture
async def app_with_webhooks(test_app: FastAPI) -> FastAPI:
    # Add the public webhook router on top of the default test app.
    test_app.include_router(stripe_webhook_router)
    return test_app


@pytest.fixture
async def webhook_client(app_with_webhooks: FastAPI):
    transport = ASGITransport(app=app_with_webhooks)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


async def test_pricing_endpoint_public_returns_defaults(client) -> None:
    r = await client.get("/v1/billing/pricing")
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {p["key"] for p in body["prices"]}
    assert keys == {"setup", "monthly"}
    amounts = {p["key"]: p["amount_cents"] for p in body["prices"]}
    assert amounts["setup"] == 250_000
    assert amounts["monthly"] == 150_000


async def test_checkout_requires_authentication(client) -> None:
    r = await client.post("/v1/billing/checkout", json={"plan": "starter"})
    assert r.status_code == 401


async def test_checkout_returns_stripe_url(auth_client) -> None:
    ac, _ = auth_client
    r = await ac.post("/v1/billing/checkout", json={"plan": "starter"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["checkout_url"].startswith("https://checkout.stripe.com/")
    assert body["session_id"].startswith("cs_test_")


async def test_checkout_unsupported_plan(auth_client) -> None:
    ac, _ = auth_client
    r = await ac.post("/v1/billing/checkout", json={"plan": "enterprise"})
    assert r.status_code == 422  # pydantic-level rejection


async def test_checkout_without_prices_returns_503(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.stripe_price_setup_id", None, raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.stripe_price_monthly_id", None, raising=False
    )
    ac, _ = auth_client
    r = await ac.post("/v1/billing/checkout", json={"plan": "starter"})
    assert r.status_code == 503


async def test_subscription_404_when_none(auth_client) -> None:
    ac, _ = auth_client
    r = await ac.get("/v1/billing/subscription")
    assert r.status_code == 404


async def test_subscription_returned_after_seed(
    auth_client, async_session
) -> None:
    ac, registered = auth_client
    me = await ac.get("/v1/auth/me")
    tenant_id = me.json()["tenant_id"]
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id=tenant_id,
        stripe_subscription_id="sub_seeded",
        status=SubscriptionStatus.ACTIVE,
    )
    await async_session.commit()
    r = await ac.get("/v1/billing/subscription")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active"
    assert body["stripe_subscription_id"] == "sub_seeded"


async def test_invoices_list_paginated(auth_client, async_session) -> None:
    ac, _ = auth_client
    me = await ac.get("/v1/auth/me")
    tenant_id = me.json()["tenant_id"]
    for i in range(3):
        await billing_service.upsert_invoice_from_stripe(
            async_session,
            tenant_id=tenant_id,
            stripe_invoice_id=f"in_{i}",
            status="paid",
            amount_due_cents=150_000,
            amount_paid_cents=150_000,
        )
    await async_session.commit()
    r = await ac.get("/v1/billing/invoices?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_invoices_cross_tenant_isolation(client, async_session) -> None:
    # Tenant A creates an invoice; tenant B must NOT see it.
    a = await register_user(client, email="a@example.com", tenant_name="A Co")
    b = await register_user(client, email="b@example.com", tenant_name="B Co")

    me_a = await client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {a.tokens.access_token}"},
    )
    tenant_a = me_a.json()["tenant_id"]
    await billing_service.upsert_invoice_from_stripe(
        async_session,
        tenant_id=tenant_a,
        stripe_invoice_id="in_for_a",
        status="paid",
        amount_due_cents=150_000,
        amount_paid_cents=150_000,
    )
    await async_session.commit()

    r = await client.get(
        "/v1/billing/invoices",
        headers={"Authorization": f"Bearer {b.tokens.access_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0


async def test_portal_409_without_customer(auth_client) -> None:
    ac, _ = auth_client
    r = await ac.post("/v1/billing/portal")
    assert r.status_code == 409


async def test_portal_returns_url_after_customer(
    auth_client, async_session
) -> None:
    ac, _ = auth_client
    me = await ac.get("/v1/auth/me")
    tenant_id = me.json()["tenant_id"]
    await billing_service.upsert_customer(
        async_session,
        tenant_id=tenant_id,
        stripe_customer_id="cus_portal",
        email_billing="billing@acme.test",
    )
    await async_session.commit()
    r = await ac.post("/v1/billing/portal")
    assert r.status_code == 200
    assert r.json()["portal_url"].startswith("https://billing.stripe.com/")


async def test_webhook_endpoint_processes_event(
    webhook_client, async_session
) -> None:
    event = {
        "id": "evt_api_1",
        "type": "customer.updated",
        "data": {"object": {"id": "cus_api_unknown", "email": "x@y.test"}},
    }
    payload = json.dumps(event).encode("utf-8")
    sig = build_mock_signature_header(payload=payload, secret=WEBHOOK_SECRET)
    r = await webhook_client.post(
        "/webhooks/stripe",
        content=payload,
        headers={
            "Stripe-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "processed"


async def test_webhook_endpoint_rejects_bad_signature(webhook_client) -> None:
    payload = json.dumps({"id": "evt_api_bad", "type": "x"}).encode("utf-8")
    r = await webhook_client.post(
        "/webhooks/stripe",
        content=payload,
        headers={
            "Stripe-Signature": "t=1,v1=deadbeef",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 400


async def test_webhook_endpoint_rejects_missing_signature(
    webhook_client,
) -> None:
    payload = json.dumps({"id": "evt_api_no_sig", "type": "x"}).encode("utf-8")
    r = await webhook_client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


async def test_pricing_uses_db_overrides_when_seeded(
    client, async_session
) -> None:
    async_session.add(
        BillingPriceConfig(
            key="monthly",
            stripe_price_id="price_seeded_monthly",
            amount_cents=999_99,
            currency="usd",
        )
    )
    await async_session.commit()
    r = await client.get("/v1/billing/pricing")
    assert r.status_code == 200
    monthly = next(p for p in r.json()["prices"] if p["key"] == "monthly")
    assert monthly["amount_cents"] == 999_99
    assert monthly["stripe_price_id"] == "price_seeded_monthly"
