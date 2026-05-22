"""Webhook signature + dispatch tests."""

from __future__ import annotations

import json

import pytest

from app.models.billing import (
    BillingEvent,
    SubscriptionStatus,
)
from app.models.tenant import Tenant
from app.services import billing_service
from app.services.billing_webhooks import process_webhook
from app.services.stripe_client import (
    StripeSignatureError,
    build_mock_signature_header,
    reset_stripe_client_cache,
)

pytestmark = pytest.mark.asyncio


WEBHOOK_SECRET = "whsec_test_unit"


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
    reset_stripe_client_cache()
    yield
    reset_stripe_client_cache()


async def _tenant(session, tenant_id: str = "t-1") -> Tenant:
    t = Tenant(id=tenant_id, name="Acme", slug=f"slug-{tenant_id}", plan="pilot")
    session.add(t)
    await session.flush()
    return t


def _signed(event: dict, *, secret: str = WEBHOOK_SECRET) -> tuple[bytes, str]:
    payload = json.dumps(event).encode("utf-8")
    sig = build_mock_signature_header(payload=payload, secret=secret)
    return payload, sig


async def test_bad_signature_rejected(async_session) -> None:
    payload = json.dumps({"id": "evt_1", "type": "invoice.paid"}).encode()
    with pytest.raises(StripeSignatureError):
        await process_webhook(
            async_session, payload=payload, sig_header="t=1,v1=deadbeef"
        )


async def test_missing_secret_raises(async_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.stripe_webhook_secret", "", raising=False
    )
    payload, sig = _signed({"id": "evt_x", "type": "invoice.paid"})
    with pytest.raises(StripeSignatureError):
        await process_webhook(async_session, payload=payload, sig_header=sig)


async def test_idempotent_duplicate_returns_already_processed(
    async_session,
) -> None:
    await _tenant(async_session)
    event = {
        "id": "evt_dup_1",
        "type": "customer.updated",
        "data": {"object": {"id": "cus_unknown", "email": "x@y.test"}},
    }
    payload, sig = _signed(event)
    r1 = await process_webhook(async_session, payload=payload, sig_header=sig)
    r2 = await process_webhook(async_session, payload=payload, sig_header=sig)
    assert r1.status == "processed"
    assert r2.status == "already_processed"


async def test_unknown_event_type_is_stored_and_ignored(async_session) -> None:
    event = {"id": "evt_unknown", "type": "weird.thing.happened", "data": {"object": {}}}
    payload, sig = _signed(event)
    r = await process_webhook(async_session, payload=payload, sig_header=sig)
    assert r.status == "ignored"
    from sqlalchemy import select

    row = (
        await async_session.execute(
            select(BillingEvent).where(BillingEvent.stripe_event_id == "evt_unknown")
        )
    ).scalar_one()
    assert row.event_type == "weird.thing.happened"
    assert row.processed_at is not None


async def test_checkout_session_completed_links_customer_and_subscription(
    async_session,
) -> None:
    await _tenant(async_session, tenant_id="t-co")
    event = {
        "id": "evt_co",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "t-co",
                "customer": "cus_co",
                "subscription": "sub_co",
                "customer_email": "owner@acme.test",
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    cust = await billing_service.get_customer_by_tenant(async_session, "t-co")
    assert cust is not None
    assert cust.stripe_customer_id == "cus_co"
    sub = await billing_service.get_subscription_by_tenant(async_session, "t-co")
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.plan_setup_paid is True


async def test_subscription_created_event_creates_projection(async_session) -> None:
    await _tenant(async_session, tenant_id="t-sc")
    await billing_service.upsert_customer(
        async_session,
        tenant_id="t-sc",
        stripe_customer_id="cus_sc",
    )
    event = {
        "id": "evt_sub_c",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_sc",
                "customer": "cus_sc",
                "status": "active",
                "current_period_start": 1_700_000_000,
                "current_period_end": 1_700_000_000 + 30 * 86_400,
                "cancel_at_period_end": False,
                "items": {
                    "data": [
                        {"price": {"unit_amount": 150000}}
                    ]
                },
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_sc"
    )
    assert sub is not None
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.monthly_price_cents == 150_000


async def test_subscription_updated_event_changes_status(async_session) -> None:
    await _tenant(async_session, tenant_id="t-up")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-up", stripe_customer_id="cus_up"
    )
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-up",
        stripe_subscription_id="sub_up",
        status=SubscriptionStatus.ACTIVE,
    )
    event = {
        "id": "evt_sub_u",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_up",
                "customer": "cus_up",
                "status": "past_due",
                "cancel_at_period_end": False,
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_up"
    )
    assert sub.status == SubscriptionStatus.PAST_DUE
    assert sub.past_due_since is not None


async def test_subscription_deleted_event_cancels(async_session) -> None:
    tenant = await _tenant(async_session, tenant_id="t-del")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-del", stripe_customer_id="cus_del"
    )
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-del",
        stripe_subscription_id="sub_del",
        status=SubscriptionStatus.ACTIVE,
    )
    event = {
        "id": "evt_sub_d",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_del",
                "customer": "cus_del",
                "status": "canceled",
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_del"
    )
    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.canceled_at is not None
    assert tenant.is_active is False


async def test_invoice_paid_drives_subscription_back_to_active(
    async_session,
) -> None:
    await _tenant(async_session, tenant_id="t-paid")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-paid", stripe_customer_id="cus_paid"
    )
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-paid",
        stripe_subscription_id="sub_paid",
        status=SubscriptionStatus.PAST_DUE,
    )
    event = {
        "id": "evt_inv_paid",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_paid",
                "customer": "cus_paid",
                "subscription": "sub_paid",
                "status": "paid",
                "amount_due": 150000,
                "amount_paid": 150000,
                "currency": "usd",
                "hosted_invoice_url": "https://invoice.example/paid",
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_paid"
    )
    assert sub.status == SubscriptionStatus.ACTIVE


async def test_invoice_payment_failed_drives_past_due(async_session) -> None:
    await _tenant(async_session, tenant_id="t-pf")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-pf", stripe_customer_id="cus_pf"
    )
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-pf",
        stripe_subscription_id="sub_pf",
        status=SubscriptionStatus.ACTIVE,
    )
    event = {
        "id": "evt_inv_fail",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_fail",
                "customer": "cus_pf",
                "subscription": "sub_pf",
                "status": "open",
                "amount_due": 150000,
                "amount_paid": 0,
                "currency": "usd",
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_pf"
    )
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_invoice_created_and_finalized_only_upsert(async_session) -> None:
    await _tenant(async_session, tenant_id="t-ic")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-ic", stripe_customer_id="cus_ic"
    )
    for evt_type, status_v in (
        ("invoice.created", "draft"),
        ("invoice.finalized", "open"),
    ):
        event = {
            "id": f"evt_{evt_type}",
            "type": evt_type,
            "data": {
                "object": {
                    "id": "in_ic",
                    "customer": "cus_ic",
                    "status": status_v,
                    "amount_due": 150000,
                    "amount_paid": 0,
                    "currency": "usd",
                }
            },
        }
        payload, sig = _signed(event)
        await process_webhook(async_session, payload=payload, sig_header=sig)
    from sqlalchemy import select

    from app.models.billing import BillingInvoice

    row = (
        await async_session.execute(
            select(BillingInvoice).where(
                BillingInvoice.stripe_invoice_id == "in_ic"
            )
        )
    ).scalar_one()
    assert row.status == "open"


async def test_customer_updated_syncs_email(async_session) -> None:
    await _tenant(async_session, tenant_id="t-eml")
    await billing_service.upsert_customer(
        async_session,
        tenant_id="t-eml",
        stripe_customer_id="cus_eml",
        email_billing="old@acme.test",
    )
    event = {
        "id": "evt_cust_up",
        "type": "customer.updated",
        "data": {"object": {"id": "cus_eml", "email": "new@acme.test"}},
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    cust = await billing_service.get_customer_by_tenant(async_session, "t-eml")
    assert cust.email_billing == "new@acme.test"


async def test_invoice_payment_action_required_drives_past_due(
    async_session,
) -> None:
    await _tenant(async_session, tenant_id="t-act")
    await billing_service.upsert_customer(
        async_session, tenant_id="t-act", stripe_customer_id="cus_act"
    )
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-act",
        stripe_subscription_id="sub_act",
        status=SubscriptionStatus.ACTIVE,
    )
    event = {
        "id": "evt_inv_act",
        "type": "invoice.payment_action_required",
        "data": {
            "object": {
                "id": "in_act",
                "customer": "cus_act",
                "subscription": "sub_act",
                "status": "open",
                "amount_due": 150000,
                "amount_paid": 0,
                "currency": "usd",
            }
        },
    }
    payload, sig = _signed(event)
    await process_webhook(async_session, payload=payload, sig_header=sig)
    sub = await billing_service.get_subscription_by_stripe_id(
        async_session, "sub_act"
    )
    assert sub.status == SubscriptionStatus.PAST_DUE
