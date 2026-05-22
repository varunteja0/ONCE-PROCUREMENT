"""Billing API endpoints.

* ``POST /v1/billing/checkout`` — create a Stripe Checkout session.
* ``POST /v1/billing/portal`` — create a Customer Portal session.
* ``GET  /v1/billing/subscription`` — current tenant's subscription state.
* ``GET  /v1/billing/invoices`` — paginated invoice cache.
* ``GET  /v1/billing/pricing`` — public-safe pricing payload for the SPA.

Tenant scoping is enforced via :data:`~app.api.deps.CurrentTenantId` /
:data:`~app.api.deps.CurrentTenantUser` — the customer / subscription /
invoice rows are loaded by tenant id, never by IDs supplied in the request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentTenantId, CurrentTenantUser
from app.config import settings
from app.db import get_db
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    InvoiceListResponse,
    InvoiceRead,
    PortalResponse,
    PriceRead,
    PricingTableResponse,
    SubscriptionRead,
)
from app.services import billing_service
from app.services.stripe_client import get_stripe_client
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/billing", tags=["billing"])
_logger = get_logger(__name__)


_PRICING_FEATURES: list[str] = [
    "Unlimited supplier submissions",
    "Signed, verifiable receipts for every submission",
    "Full audit trail + SOC 2 evidence export",
    "Founder-led onboarding ($2,500 one-time)",
    "$1,500/mo subscription — cancel anytime",
]


@router.get(
    "/pricing",
    response_model=PricingTableResponse,
    summary="Public pricing payload for the marketing + billing pages",
)
async def get_pricing(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PricingTableResponse:
    defaults = billing_service.cents_for_plan()
    setup_cfg = await billing_service.get_price_config(session, "setup")
    monthly_cfg = await billing_service.get_price_config(session, "monthly")
    prices = [
        PriceRead(
            key="setup",
            stripe_price_id=setup_cfg.stripe_price_id if setup_cfg else None,
            amount_cents=setup_cfg.amount_cents if setup_cfg else defaults.setup_cents,
            currency=setup_cfg.currency if setup_cfg else "usd",
            label="One-time setup",
            description="Founder-led onboarding, portal mapping, and signing key install.",
        ),
        PriceRead(
            key="monthly",
            stripe_price_id=monthly_cfg.stripe_price_id if monthly_cfg else None,
            amount_cents=monthly_cfg.amount_cents
            if monthly_cfg
            else defaults.monthly_cents,
            currency=monthly_cfg.currency if monthly_cfg else "usd",
            label="Monthly subscription",
            description="Unlimited submissions, receipts, and audit exports.",
        ),
    ]
    return PricingTableResponse(prices=prices, features=_PRICING_FEATURES)


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Stripe Checkout session for the current tenant",
)
async def create_checkout(
    payload: CheckoutRequest,
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutResponse:
    if payload.plan != "starter":
        raise HTTPException(status_code=400, detail="unsupported_plan")

    setup_cfg = await billing_service.get_price_config(session, "setup")
    monthly_cfg = await billing_service.get_price_config(session, "monthly")
    setup_price_id = (
        setup_cfg.stripe_price_id if setup_cfg else settings.stripe_price_setup_id
    )
    monthly_price_id = (
        monthly_cfg.stripe_price_id
        if monthly_cfg
        else settings.stripe_price_monthly_id
    )
    if not setup_price_id or not monthly_price_id:
        raise HTTPException(
            status_code=503,
            detail="billing_not_configured",
        )

    customer = await billing_service.get_customer_by_tenant(
        session, tenant_user.tenant_id
    )
    line_items = [
        {"price": setup_price_id, "quantity": 1},
        {"price": monthly_price_id, "quantity": 1},
    ]
    client = get_stripe_client()
    cs = client.create_checkout_session(
        customer_email=None,
        customer_id=customer.stripe_customer_id if customer else None,
        client_reference_id=tenant_user.tenant_id,
        line_items=line_items,
        success_url=settings.stripe_checkout_success_url,
        cancel_url=settings.stripe_checkout_cancel_url,
        metadata={
            "tenant_id": tenant_user.tenant_id,
            "user_id": tenant_user.user_id,
        },
    )
    _logger.info(
        "billing.checkout_created",
        tenant_id=tenant_user.tenant_id,
        session_id=cs.get("id"),
    )
    return CheckoutResponse(
        checkout_url=str(cs["url"]),
        session_id=str(cs["id"]),
    )


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create a Stripe Customer Portal session for the current tenant",
)
async def create_portal_session(
    tenant_user: CurrentTenantUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortalResponse:
    customer = await billing_service.get_customer_by_tenant(
        session, tenant_user.tenant_id
    )
    if customer is None:
        raise HTTPException(
            status_code=409,
            detail="no_billing_customer",
        )
    client = get_stripe_client()
    portal = client.create_billing_portal_session(
        customer_id=customer.stripe_customer_id,
        return_url=settings.stripe_customer_portal_return_url,
    )
    return PortalResponse(portal_url=str(portal["url"]))


@router.get(
    "/subscription",
    response_model=SubscriptionRead,
    summary="Current tenant subscription state",
)
async def get_subscription(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionRead:
    sub = await billing_service.get_subscription_by_tenant(session, tenant_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="no_subscription")
    # Lazily advance past_due → unpaid when the grace window has expired.
    await billing_service.apply_grace_period(session, sub)
    return SubscriptionRead.model_validate(sub)


@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="Paginated invoice cache for the current tenant",
)
async def list_invoices(
    tenant_id: CurrentTenantId,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    items, total = await billing_service.list_invoices_for_tenant(
        session, tenant_id=tenant_id, limit=limit, offset=offset
    )
    return InvoiceListResponse(
        items=[InvoiceRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
