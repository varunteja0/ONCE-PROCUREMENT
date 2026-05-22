"""Pydantic schemas for the billing API surface."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CheckoutRequest",
    "CheckoutResponse",
    "PortalResponse",
    "SubscriptionRead",
    "InvoiceRead",
    "InvoiceListResponse",
    "PriceRead",
    "PricingTableResponse",
    "WebhookAck",
]


PlanKey = Literal["starter"]


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: PlanKey = Field(default="starter", description="Selected plan key.")


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    stripe_subscription_id: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    plan_setup_paid: bool = False
    monthly_price_cents: int = 0
    past_due_since: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stripe_invoice_id: str
    status: str
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    hosted_invoice_url: str | None = None
    invoice_pdf_url: str | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceRead]
    total: int
    limit: int
    offset: int


class PriceRead(BaseModel):
    key: str
    stripe_price_id: str | None = None
    amount_cents: int
    currency: str = "usd"
    label: str
    description: str


class PricingTableResponse(BaseModel):
    plan_name: str = "Starter"
    plan_tagline: str = "Submit once. Prove it forever."
    prices: list[PriceRead]
    features: list[str]


class WebhookAck(BaseModel):
    status: Literal["processed", "already_processed", "ignored"] = "processed"
    event_id: str | None = None
