"""L3.5 - Stripe billing tables.

Revision ID: 20260521_02_billing
Revises: 20260521_01_cockpit_roles
Create Date: 2026-05-21

Adds:

* billing_customers          - 1:1 tenant <-> Stripe Customer
* billing_subscriptions      - projection of current Stripe Subscription
* billing_invoices           - append-only invoice cache
* billing_events             - webhook ledger (idempotency)
* billing_price_configs      - Stripe Price IDs seeded per env
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_02_billing"
down_revision: Union[str, None] = "20260521_01_cockpit_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("email_billing", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_billing_customers_tenant"),
    )
    op.create_index("ix_billing_customers_tenant_id", "billing_customers", ["tenant_id"])
    op.create_index(
        "ix_billing_customers_stripe_customer_id",
        "billing_customers",
        ["stripe_customer_id"],
    )

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_subscription_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_invoice_id", sa.String(length=64), nullable=True),
        sa.Column("plan_setup_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False, server_default="150000"),
        sa.Column("past_due_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_subscriptions_tenant_id", "billing_subscriptions", ["tenant_id"])
    op.create_index(
        "ix_billing_subscriptions_stripe_subscription_id",
        "billing_subscriptions",
        ["stripe_subscription_id"],
    )

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_invoice_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_due_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("hosted_invoice_url", sa.String(length=1024), nullable=True),
        sa.Column("invoice_pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_invoices_tenant_id", "billing_invoices", ["tenant_id"])
    op.create_index("ix_billing_invoices_stripe_invoice_id", "billing_invoices", ["stripe_invoice_id"])

    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("stripe_event_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_billing_events_stripe_event_id", "billing_events", ["stripe_event_id"])
    op.create_index("ix_billing_events_event_type", "billing_events", ["event_type"])

    op.create_table(
        "billing_price_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key", name="uq_billing_price_configs_key"),
    )
    op.create_index("ix_billing_price_configs_key", "billing_price_configs", ["key"])


def downgrade() -> None:
    op.drop_index("ix_billing_price_configs_key", table_name="billing_price_configs")
    op.drop_table("billing_price_configs")
    op.drop_index("ix_billing_events_event_type", table_name="billing_events")
    op.drop_index("ix_billing_events_stripe_event_id", table_name="billing_events")
    op.drop_table("billing_events")
    op.drop_index("ix_billing_invoices_stripe_invoice_id", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_tenant_id", table_name="billing_invoices")
    op.drop_table("billing_invoices")
    op.drop_index("ix_billing_subscriptions_stripe_subscription_id", table_name="billing_subscriptions")
    op.drop_index("ix_billing_subscriptions_tenant_id", table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
    op.drop_index("ix_billing_customers_stripe_customer_id", table_name="billing_customers")
    op.drop_index("ix_billing_customers_tenant_id", table_name="billing_customers")
    op.drop_table("billing_customers")
