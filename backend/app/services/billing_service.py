"""Pure-domain billing service.

Stripe is the system of record; this module owns the **projection** logic:
the state machine, idempotent upserts, and tenant-side feature gating. It
deliberately does NOT import :mod:`stripe` — the only Stripe-touching code
lives in :mod:`app.services.stripe_client` and the webhook dispatcher.

State machine for :attr:`BillingSubscription.status` (see ``docs/BILLING.md``):

* ``incomplete`` → ``trialing`` | ``active``
* ``active`` → ``past_due`` → ``unpaid`` (after grace) → ``canceled``
* ``active`` → ``canceled`` (immediate)
* ``active`` ↔ ``paused``

Feature gating:

* ``past_due`` / ``unpaid``  → ``tenant.feature_flags.billing_grace_warning = True``
* ``canceled`` (terminal)    → ``tenant.is_active = False``
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import (
    BillingCustomer,
    BillingInvoice,
    BillingPriceConfig,
    BillingSubscription,
    SubscriptionStatus,
)
from app.models.tenant import Tenant
from app.utils.logging import get_logger

__all__ = [
    "BillingStateError",
    "ALLOWED_TRANSITIONS",
    "is_allowed_transition",
    "transition_status",
    "apply_grace_period",
    "upsert_customer",
    "get_customer_by_tenant",
    "get_customer_by_stripe_id",
    "get_subscription_by_tenant",
    "get_subscription_by_stripe_id",
    "upsert_subscription_from_stripe",
    "upsert_invoice_from_stripe",
    "list_invoices_for_tenant",
    "set_setup_paid",
    "pause_subscription",
    "resume_subscription",
    "cents_for_plan",
    "get_price_config",
    "redact_email",
]


_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


# Explicit adjacency map. We accept Stripe-sourced status changes liberally
# (Stripe may skip intermediate states under retries) but the operator-driven
# ``pause``/``resume`` paths use :func:`transition_status` strictly.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    SubscriptionStatus.INCOMPLETE: frozenset(
        {
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.INCOMPLETE,
        }
    ),
    SubscriptionStatus.TRIALING: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.TRIALING,
        }
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.UNPAID,
            SubscriptionStatus.ACTIVE,
        }
    ),
    SubscriptionStatus.PAST_DUE: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.UNPAID,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.PAST_DUE,
        }
    ),
    SubscriptionStatus.UNPAID: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.UNPAID,
        }
    ),
    SubscriptionStatus.PAUSED: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.PAUSED,
        }
    ),
    SubscriptionStatus.CANCELED: frozenset(
        {SubscriptionStatus.CANCELED}  # terminal
    ),
}


class BillingStateError(Exception):
    """Raised on disallowed state transitions or invalid billing operations."""


def is_allowed_transition(*, from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# PII helpers
# ---------------------------------------------------------------------------


def redact_email(email: str | None) -> str:
    """Return a log-safe form of an email (``j***@example.com``)."""

    if not email or "@" not in email:
        return "<redacted>"
    local, _, domain = email.partition("@")
    if not local:
        return f"<redacted>@{domain}"
    return f"{local[0]}***@{domain}"


# ---------------------------------------------------------------------------
# Customer CRUD
# ---------------------------------------------------------------------------


async def get_customer_by_tenant(
    session: AsyncSession, tenant_id: str
) -> BillingCustomer | None:
    res = await session.execute(
        select(BillingCustomer).where(BillingCustomer.tenant_id == tenant_id)
    )
    return res.scalar_one_or_none()


async def get_customer_by_stripe_id(
    session: AsyncSession, stripe_customer_id: str
) -> BillingCustomer | None:
    res = await session.execute(
        select(BillingCustomer).where(
            BillingCustomer.stripe_customer_id == stripe_customer_id
        )
    )
    return res.scalar_one_or_none()


async def upsert_customer(
    session: AsyncSession,
    *,
    tenant_id: str,
    stripe_customer_id: str,
    email_billing: str | None = None,
) -> BillingCustomer:
    existing = await get_customer_by_tenant(session, tenant_id)
    if existing is not None:
        existing.stripe_customer_id = stripe_customer_id
        if email_billing is not None:
            existing.email_billing = email_billing
        await session.flush()
        return existing
    customer = BillingCustomer(
        tenant_id=tenant_id,
        stripe_customer_id=stripe_customer_id,
        email_billing=email_billing,
    )
    session.add(customer)
    await session.flush()
    return customer


# ---------------------------------------------------------------------------
# Subscription state machine
# ---------------------------------------------------------------------------


async def get_subscription_by_tenant(
    session: AsyncSession, tenant_id: str
) -> BillingSubscription | None:
    res = await session.execute(
        select(BillingSubscription)
        .where(BillingSubscription.tenant_id == tenant_id)
        .order_by(desc(BillingSubscription.created_at))
    )
    return res.scalars().first()


async def get_subscription_by_stripe_id(
    session: AsyncSession, stripe_subscription_id: str
) -> BillingSubscription | None:
    res = await session.execute(
        select(BillingSubscription).where(
            BillingSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )
    return res.scalar_one_or_none()


async def _apply_tenant_gating(
    session: AsyncSession, *, tenant_id: str, status: str
) -> None:
    """Apply tenant-level effects of a subscription status change.

    * grace warning flag toggled for past_due/unpaid
    * tenant deactivated (``is_active=False``) on canceled
    """

    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if tenant is None:
        return
    if status == SubscriptionStatus.CANCELED:
        tenant.is_active = False
    elif status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}:
        tenant.is_active = True


def _coerce_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(int(value), tz=UTC)
    return None


async def transition_status(
    session: AsyncSession,
    subscription: BillingSubscription,
    *,
    to_status: str,
    strict: bool = False,
) -> BillingSubscription:
    """Move a subscription to ``to_status``.

    When ``strict`` is True a disallowed transition raises
    :class:`BillingStateError`. When ``strict`` is False (the default for
    webhook-driven syncs) the transition is logged and the new status applied
    anyway — Stripe is authoritative.
    """

    if to_status not in SubscriptionStatus.ALL:
        raise BillingStateError(f"unknown subscription status: {to_status!r}")
    if not is_allowed_transition(
        from_status=subscription.status, to_status=to_status
    ):
        if strict:
            raise BillingStateError(
                f"disallowed transition {subscription.status} -> {to_status}"
            )
        _logger.warning(
            "billing.unexpected_transition",
            tenant_id=subscription.tenant_id,
            from_status=subscription.status,
            to_status=to_status,
        )
    previous = subscription.status
    subscription.status = to_status

    now = _now()
    if to_status == SubscriptionStatus.PAST_DUE and previous != SubscriptionStatus.PAST_DUE:
        subscription.past_due_since = now
    if to_status == SubscriptionStatus.ACTIVE:
        subscription.past_due_since = None
    if to_status == SubscriptionStatus.CANCELED and subscription.canceled_at is None:
        subscription.canceled_at = now

    await _apply_tenant_gating(
        session, tenant_id=subscription.tenant_id, status=to_status
    )
    await session.flush()
    return subscription


async def apply_grace_period(
    session: AsyncSession,
    subscription: BillingSubscription,
    *,
    now: datetime | None = None,
    grace_days: int | None = None,
) -> BillingSubscription:
    """If ``past_due`` longer than ``grace_days``, move to ``unpaid``.

    Idempotent — re-running before the grace window expires is a no-op.
    """

    if subscription.status != SubscriptionStatus.PAST_DUE:
        return subscription
    if subscription.past_due_since is None:
        return subscription
    eff_now = now or _now()
    days = (
        grace_days
        if grace_days is not None
        else settings.billing_grace_period_days
    )
    boundary = subscription.past_due_since + timedelta(days=days)
    if eff_now >= boundary:
        await transition_status(
            session, subscription, to_status=SubscriptionStatus.UNPAID
        )
    return subscription


async def pause_subscription(
    session: AsyncSession, subscription: BillingSubscription
) -> BillingSubscription:
    return await transition_status(
        session, subscription, to_status=SubscriptionStatus.PAUSED, strict=True
    )


async def resume_subscription(
    session: AsyncSession, subscription: BillingSubscription
) -> BillingSubscription:
    return await transition_status(
        session, subscription, to_status=SubscriptionStatus.ACTIVE, strict=True
    )


async def set_setup_paid(
    session: AsyncSession, subscription: BillingSubscription
) -> BillingSubscription:
    subscription.plan_setup_paid = True
    await session.flush()
    return subscription


# ---------------------------------------------------------------------------
# Subscription / invoice upserts (called from webhook handlers)
# ---------------------------------------------------------------------------


async def upsert_subscription_from_stripe(
    session: AsyncSession,
    *,
    tenant_id: str,
    stripe_subscription_id: str,
    status: str,
    current_period_start: Any = None,
    current_period_end: Any = None,
    cancel_at_period_end: bool = False,
    canceled_at: Any = None,
    latest_invoice_id: str | None = None,
    monthly_price_cents: int | None = None,
) -> BillingSubscription:
    sub = await get_subscription_by_stripe_id(session, stripe_subscription_id)
    if sub is None:
        sub = BillingSubscription(
            tenant_id=tenant_id,
            stripe_subscription_id=stripe_subscription_id,
            status=SubscriptionStatus.INCOMPLETE,
            monthly_price_cents=monthly_price_cents or 150_000,
        )
        session.add(sub)
        await session.flush()

    sub.current_period_start = _coerce_dt(current_period_start) or sub.current_period_start
    sub.current_period_end = _coerce_dt(current_period_end) or sub.current_period_end
    sub.cancel_at_period_end = bool(cancel_at_period_end)
    coerced_cancel = _coerce_dt(canceled_at)
    if coerced_cancel is not None:
        sub.canceled_at = coerced_cancel
    if latest_invoice_id:
        sub.latest_invoice_id = latest_invoice_id
    if monthly_price_cents is not None:
        sub.monthly_price_cents = monthly_price_cents

    if status and status != sub.status:
        await transition_status(session, sub, to_status=status, strict=False)
    else:
        await _apply_tenant_gating(
            session, tenant_id=sub.tenant_id, status=sub.status
        )
    return sub


async def upsert_invoice_from_stripe(
    session: AsyncSession,
    *,
    tenant_id: str,
    stripe_invoice_id: str,
    status: str,
    amount_due_cents: int,
    amount_paid_cents: int,
    currency: str = "usd",
    hosted_invoice_url: str | None = None,
    invoice_pdf_url: str | None = None,
    due_at: Any = None,
    paid_at: Any = None,
) -> BillingInvoice:
    res = await session.execute(
        select(BillingInvoice).where(
            BillingInvoice.stripe_invoice_id == stripe_invoice_id
        )
    )
    inv = res.scalar_one_or_none()
    if inv is None:
        inv = BillingInvoice(
            tenant_id=tenant_id,
            stripe_invoice_id=stripe_invoice_id,
            status=status,
            amount_due_cents=amount_due_cents,
            amount_paid_cents=amount_paid_cents,
            currency=currency,
            hosted_invoice_url=hosted_invoice_url,
            invoice_pdf_url=invoice_pdf_url,
            due_at=_coerce_dt(due_at),
            paid_at=_coerce_dt(paid_at),
        )
        session.add(inv)
    else:
        inv.status = status
        inv.amount_due_cents = amount_due_cents
        inv.amount_paid_cents = amount_paid_cents
        inv.currency = currency or inv.currency
        if hosted_invoice_url:
            inv.hosted_invoice_url = hosted_invoice_url
        if invoice_pdf_url:
            inv.invoice_pdf_url = invoice_pdf_url
        coerced_due = _coerce_dt(due_at)
        if coerced_due is not None:
            inv.due_at = coerced_due
        coerced_paid = _coerce_dt(paid_at)
        if coerced_paid is not None:
            inv.paid_at = coerced_paid
    await session.flush()
    return inv


async def list_invoices_for_tenant(
    session: AsyncSession,
    *,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BillingInvoice], int]:
    from sqlalchemy import func as _func

    total_res = await session.execute(
        select(_func.count(BillingInvoice.id)).where(
            BillingInvoice.tenant_id == tenant_id
        )
    )
    total = int(total_res.scalar_one() or 0)
    res = await session.execute(
        select(BillingInvoice)
        .where(BillingInvoice.tenant_id == tenant_id)
        .order_by(desc(BillingInvoice.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(res.scalars().all()), total


# ---------------------------------------------------------------------------
# Price config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PlanDefaults:
    setup_cents: int = 250_000  # $2,500
    monthly_cents: int = 150_000  # $1,500


PLAN_DEFAULTS = _PlanDefaults()


def cents_for_plan() -> _PlanDefaults:
    return PLAN_DEFAULTS


async def get_price_config(
    session: AsyncSession, key: str
) -> BillingPriceConfig | None:
    res = await session.execute(
        select(BillingPriceConfig).where(
            BillingPriceConfig.key == key, BillingPriceConfig.active.is_(True)
        )
    )
    return res.scalar_one_or_none()


__all__.append("PLAN_DEFAULTS")
