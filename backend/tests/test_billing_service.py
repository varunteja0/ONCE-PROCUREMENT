"""Unit tests for billing_service — state machine + projection helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.billing import (
    BillingSubscription,
    SubscriptionStatus,
)
from app.models.tenant import Tenant
from app.services import billing_service
from app.services.billing_service import BillingStateError


async def _make_tenant(session, *, tenant_id: str = "t-1") -> Tenant:
    t = Tenant(id=tenant_id, name="Acme", slug=f"slug-{tenant_id}", plan="pilot")
    session.add(t)
    await session.flush()
    return t


async def _make_sub(
    session, *, tenant_id: str = "t-1", status: str = SubscriptionStatus.INCOMPLETE
) -> BillingSubscription:
    sub = BillingSubscription(
        tenant_id=tenant_id,
        stripe_subscription_id=f"sub_{tenant_id}_{status}",
        status=status,
        monthly_price_cents=150_000,
    )
    session.add(sub)
    await session.flush()
    return sub


def test_is_allowed_transition_table() -> None:
    assert billing_service.is_allowed_transition(
        from_status=SubscriptionStatus.INCOMPLETE,
        to_status=SubscriptionStatus.ACTIVE,
    )
    assert billing_service.is_allowed_transition(
        from_status=SubscriptionStatus.ACTIVE,
        to_status=SubscriptionStatus.PAST_DUE,
    )
    assert not billing_service.is_allowed_transition(
        from_status=SubscriptionStatus.CANCELED,
        to_status=SubscriptionStatus.ACTIVE,
    )


def test_redact_email_basic() -> None:
    assert billing_service.redact_email("jane@example.com") == "j***@example.com"
    assert billing_service.redact_email(None) == "<redacted>"
    assert billing_service.redact_email("nope") == "<redacted>"


async def test_transition_incomplete_to_active(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.INCOMPLETE)
    await billing_service.transition_status(
        async_session, sub, to_status=SubscriptionStatus.ACTIVE
    )
    assert sub.status == SubscriptionStatus.ACTIVE


async def test_transition_active_to_past_due_sets_past_due_since(
    async_session,
) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    await billing_service.transition_status(
        async_session, sub, to_status=SubscriptionStatus.PAST_DUE
    )
    assert sub.status == SubscriptionStatus.PAST_DUE
    assert sub.past_due_since is not None


async def test_transition_past_due_back_to_active_clears_marker(
    async_session,
) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.PAST_DUE)
    sub.past_due_since = datetime.now(UTC)
    await billing_service.transition_status(
        async_session, sub, to_status=SubscriptionStatus.ACTIVE
    )
    assert sub.past_due_since is None


async def test_transition_active_to_canceled_immediate(async_session) -> None:
    tenant = await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    await billing_service.transition_status(
        async_session, sub, to_status=SubscriptionStatus.CANCELED
    )
    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.canceled_at is not None
    assert tenant.is_active is False


async def test_transition_strict_rejects_invalid(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.CANCELED)
    with pytest.raises(BillingStateError):
        await billing_service.transition_status(
            async_session,
            sub,
            to_status=SubscriptionStatus.ACTIVE,
            strict=True,
        )


async def test_transition_non_strict_logs_but_applies(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.UNPAID)
    # unpaid -> past_due is not in the table but non-strict should let Stripe win.
    await billing_service.transition_status(
        async_session,
        sub,
        to_status=SubscriptionStatus.PAST_DUE,
        strict=False,
    )
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_transition_unknown_status_raises(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    with pytest.raises(BillingStateError):
        await billing_service.transition_status(
            async_session, sub, to_status="bogus"
        )


async def test_pause_and_resume(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    await billing_service.pause_subscription(async_session, sub)
    assert sub.status == SubscriptionStatus.PAUSED
    await billing_service.resume_subscription(async_session, sub)
    assert sub.status == SubscriptionStatus.ACTIVE


async def test_apply_grace_period_within_window_is_noop(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.PAST_DUE)
    sub.past_due_since = datetime.now(UTC) - timedelta(days=3)
    await billing_service.apply_grace_period(async_session, sub, grace_days=7)
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_apply_grace_period_boundary_moves_to_unpaid(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.PAST_DUE)
    sub.past_due_since = datetime.now(UTC) - timedelta(days=8)
    await billing_service.apply_grace_period(async_session, sub, grace_days=7)
    assert sub.status == SubscriptionStatus.UNPAID


async def test_upsert_customer_new_then_idempotent(async_session) -> None:
    await _make_tenant(async_session)
    c1 = await billing_service.upsert_customer(
        async_session,
        tenant_id="t-1",
        stripe_customer_id="cus_abc",
        email_billing="billing@acme.test",
    )
    c2 = await billing_service.upsert_customer(
        async_session,
        tenant_id="t-1",
        stripe_customer_id="cus_abc",
        email_billing="billing@acme.test",
    )
    assert c1.id == c2.id


async def test_upsert_subscription_creates_and_syncs(async_session) -> None:
    await _make_tenant(async_session)
    sub = await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-1",
        stripe_subscription_id="sub_x",
        status=SubscriptionStatus.ACTIVE,
        current_period_start=1_700_000_000,
        current_period_end=1_700_000_000 + 30 * 86_400,
        monthly_price_cents=150_000,
    )
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.current_period_start is not None


async def test_upsert_invoice_creates_and_updates(async_session) -> None:
    await _make_tenant(async_session)
    inv = await billing_service.upsert_invoice_from_stripe(
        async_session,
        tenant_id="t-1",
        stripe_invoice_id="in_1",
        status="open",
        amount_due_cents=150_000,
        amount_paid_cents=0,
    )
    assert inv.status == "open"
    inv2 = await billing_service.upsert_invoice_from_stripe(
        async_session,
        tenant_id="t-1",
        stripe_invoice_id="in_1",
        status="paid",
        amount_due_cents=150_000,
        amount_paid_cents=150_000,
    )
    assert inv2.id == inv.id
    assert inv2.status == "paid"


async def test_list_invoices_only_returns_tenant_rows(async_session) -> None:
    await _make_tenant(async_session, tenant_id="t-a")
    await _make_tenant(async_session, tenant_id="t-b")
    await billing_service.upsert_invoice_from_stripe(
        async_session,
        tenant_id="t-a",
        stripe_invoice_id="in_a",
        status="paid",
        amount_due_cents=100,
        amount_paid_cents=100,
    )
    await billing_service.upsert_invoice_from_stripe(
        async_session,
        tenant_id="t-b",
        stripe_invoice_id="in_b",
        status="paid",
        amount_due_cents=200,
        amount_paid_cents=200,
    )
    items, total = await billing_service.list_invoices_for_tenant(
        async_session, tenant_id="t-a"
    )
    assert total == 1
    assert items[0].stripe_invoice_id == "in_a"


async def test_set_setup_paid_flag(async_session) -> None:
    await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    assert sub.plan_setup_paid is False
    await billing_service.set_setup_paid(async_session, sub)
    assert sub.plan_setup_paid is True


async def test_cents_for_plan_defaults_match_phase2_pricing() -> None:
    defaults = billing_service.cents_for_plan()
    assert defaults.setup_cents == 250_000  # $2,500
    assert defaults.monthly_cents == 150_000  # $1,500


async def test_canceled_tenant_is_deactivated(async_session) -> None:
    tenant = await _make_tenant(async_session)
    sub = await _make_sub(async_session, status=SubscriptionStatus.ACTIVE)
    await billing_service.upsert_subscription_from_stripe(
        async_session,
        tenant_id="t-1",
        stripe_subscription_id=sub.stripe_subscription_id,
        status=SubscriptionStatus.CANCELED,
    )
    assert tenant.is_active is False
