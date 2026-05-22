"""Billing models — Stripe-mirrored state for tenants.

Tables stay portable across Postgres + SQLite (no native enums, no PG-only
functions). Stripe is the system of record; these tables are a cached
projection so the API can answer "what's this tenant's billing status?"
without hitting Stripe on every request.

Tables:

* :class:`BillingCustomer` — 1:1 with :class:`~app.models.tenant.Tenant`.
* :class:`BillingSubscription` — one per tenant (current subscription).
* :class:`BillingInvoice` — append-only invoice cache.
* :class:`BillingEvent` — webhook ledger (idempotency + audit).
* :class:`BillingPriceConfig` — seeded by ``seed_stripe_prices.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, _uuid

# ---------------------------------------------------------------------------
# String-enum constants (kept here as module attrs — no native enum types so
# SQLite portability is preserved).
# ---------------------------------------------------------------------------


class SubscriptionStatus:
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    PAUSED = "paused"

    ALL: tuple[str, ...] = (
        INCOMPLETE,
        TRIALING,
        ACTIVE,
        PAST_DUE,
        CANCELED,
        UNPAID,
        PAUSED,
    )


class InvoiceStatus:
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"

    ALL: tuple[str, ...] = (DRAFT, OPEN, PAID, UNCOLLECTIBLE, VOID)


class PriceKey:
    SETUP = "setup"
    MONTHLY = "monthly"

    ALL: tuple[str, ...] = (SETUP, MONTHLY)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class BillingCustomer(Base, TimestampMixin):
    """1:1 link between a Tenant and a Stripe Customer."""

    __tablename__ = "billing_customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_billing_customers_tenant"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    email_billing: Mapped[str | None] = mapped_column(
        String(320), nullable=True
    )


class BillingSubscription(Base, TimestampMixin):
    """Cached projection of a tenant's current Stripe Subscription."""

    __tablename__ = "billing_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SubscriptionStatus.INCOMPLETE
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latest_invoice_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    plan_setup_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    monthly_price_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=150_000
    )
    # When the subscription first entered ``past_due``; used to compute the
    # grace-period boundary before transitioning to ``unpaid``.
    past_due_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BillingInvoice(Base, TimestampMixin):
    """Append-only invoice cache."""

    __tablename__ = "billing_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_invoice_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_due_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    hosted_invoice_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    invoice_pdf_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BillingEvent(Base):
    """Webhook ledger — idempotency + audit trail.

    Inserted on the first webhook receipt for a given Stripe event id; any
    subsequent delivery of the same event short-circuits to a 200 OK without
    re-running handlers.
    """

    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    stripe_event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class BillingPriceConfig(Base, TimestampMixin):
    """Stripe Price IDs the app uses, seeded once per environment."""

    __tablename__ = "billing_price_configs"
    __table_args__ = (
        UniqueConstraint("key", name="uq_billing_price_configs_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stripe_price_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


__all__ = [
    "BillingCustomer",
    "BillingSubscription",
    "BillingInvoice",
    "BillingEvent",
    "BillingPriceConfig",
    "SubscriptionStatus",
    "InvoiceStatus",
    "PriceKey",
]
