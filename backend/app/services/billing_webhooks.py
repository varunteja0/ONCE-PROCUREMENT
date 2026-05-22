"""Stripe webhook dispatch.

Flow on every POST to ``/webhooks/stripe``:

1. Verify the Stripe-Signature header using the configured webhook secret.
2. Claim the event via :func:`app.utils.idempotent_event.claim_event`. If the
   event was already claimed, short-circuit with ``already_processed``.
3. Dispatch to the per-event handler; unknown events are stored + acked.
4. Stamp ``processed_at`` on success; store the truncated error otherwise.

The handler functions accept the parsed event dict and an
:class:`AsyncSession`; they never call Stripe. Any state change is via the
:mod:`app.services.billing_service` API so the state machine stays in one
place.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import InvoiceStatus, SubscriptionStatus
from app.services import billing_service
from app.services.stripe_client import (
    StripeSignatureError,
    get_stripe_client,
)
from app.utils.idempotent_event import (
    claim_event,
    mark_failed,
    mark_processed,
)
from app.utils.logging import get_logger

__all__ = [
    "process_webhook",
    "verify_signature",
    "HANDLED_EVENT_TYPES",
    "WebhookResult",
]


_logger = get_logger(__name__)


HANDLED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.created",
        "invoice.finalized",
        "invoice.paid",
        "invoice.payment_failed",
        "invoice.payment_action_required",
        "customer.updated",
    }
)


class WebhookResult:
    """Tiny return record for the API layer."""

    __slots__ = ("status", "event_id", "error")

    def __init__(
        self,
        *,
        status: str,
        event_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.status = status
        self.event_id = event_id
        self.error = error


def verify_signature(
    *, payload: bytes, sig_header: str, secret: str | None = None
) -> dict[str, Any]:
    """Verify the Stripe signature and return the parsed event payload."""

    effective_secret = secret or settings.stripe_webhook_secret or ""
    if not effective_secret:
        raise StripeSignatureError("webhook secret not configured")
    client = get_stripe_client()
    return client.construct_event(
        payload=payload, sig_header=sig_header, secret=effective_secret
    )


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------


def _data_object(event: dict[str, Any]) -> dict[str, Any]:
    return ((event.get("data") or {}).get("object")) or {}


async def _resolve_tenant_id(
    session: AsyncSession, *, customer_id: str | None, fallback: str | None = None
) -> str | None:
    if fallback:
        return fallback
    if not customer_id:
        return None
    cust = await billing_service.get_customer_by_stripe_id(session, customer_id)
    return cust.tenant_id if cust else None


def _first_line_price_amount(obj: dict[str, Any]) -> int | None:
    lines = obj.get("items") or {}
    data = lines.get("data") if isinstance(lines, dict) else None
    if not data:
        return None
    price = (data[0] or {}).get("price") or {}
    amount = price.get("unit_amount")
    return int(amount) if isinstance(amount, int) else None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_checkout_completed(
    session: AsyncSession, event: dict[str, Any]
) -> None:
    obj = _data_object(event)
    tenant_id = obj.get("client_reference_id")
    if not tenant_id:
        _logger.warning(
            "billing.webhook.checkout_missing_tenant", event_id=event.get("id")
        )
        return
    customer_id = obj.get("customer")
    subscription_id = obj.get("subscription")
    email = obj.get("customer_email") or (obj.get("customer_details") or {}).get(
        "email"
    )

    if customer_id:
        await billing_service.upsert_customer(
            session,
            tenant_id=str(tenant_id),
            stripe_customer_id=str(customer_id),
            email_billing=email,
        )

    if subscription_id:
        sub = await billing_service.upsert_subscription_from_stripe(
            session,
            tenant_id=str(tenant_id),
            stripe_subscription_id=str(subscription_id),
            status=SubscriptionStatus.ACTIVE,
        )
        await billing_service.set_setup_paid(session, sub)

    _logger.info(
        "billing.webhook.checkout_completed",
        tenant_id=str(tenant_id),
        subscription_id=subscription_id,
        billing_email=billing_service.redact_email(email),
    )


async def _handle_subscription_event(
    session: AsyncSession, event: dict[str, Any]
) -> None:
    obj = _data_object(event)
    sub_id = obj.get("id")
    if not sub_id:
        return
    customer_id = obj.get("customer")
    tenant_id = await _resolve_tenant_id(session, customer_id=customer_id)
    existing = await billing_service.get_subscription_by_stripe_id(session, str(sub_id))
    effective_tenant = tenant_id or (existing.tenant_id if existing else None)
    if not effective_tenant:
        _logger.warning(
            "billing.webhook.subscription_unknown_tenant",
            event_id=event.get("id"),
            stripe_subscription_id=sub_id,
        )
        return
    status = obj.get("status") or SubscriptionStatus.INCOMPLETE
    if event.get("type") == "customer.subscription.deleted":
        status = SubscriptionStatus.CANCELED
    await billing_service.upsert_subscription_from_stripe(
        session,
        tenant_id=str(effective_tenant),
        stripe_subscription_id=str(sub_id),
        status=str(status),
        current_period_start=obj.get("current_period_start"),
        current_period_end=obj.get("current_period_end"),
        cancel_at_period_end=bool(obj.get("cancel_at_period_end")),
        canceled_at=obj.get("canceled_at"),
        latest_invoice_id=obj.get("latest_invoice"),
        monthly_price_cents=_first_line_price_amount(obj),
    )


async def _handle_invoice_event(
    session: AsyncSession, event: dict[str, Any]
) -> None:
    obj = _data_object(event)
    invoice_id = obj.get("id")
    if not invoice_id:
        return
    customer_id = obj.get("customer")
    tenant_id = await _resolve_tenant_id(session, customer_id=customer_id)
    if not tenant_id:
        _logger.warning(
            "billing.webhook.invoice_unknown_tenant",
            event_id=event.get("id"),
            stripe_invoice_id=invoice_id,
        )
        return

    status = obj.get("status") or InvoiceStatus.OPEN
    await billing_service.upsert_invoice_from_stripe(
        session,
        tenant_id=tenant_id,
        stripe_invoice_id=str(invoice_id),
        status=str(status),
        amount_due_cents=int(obj.get("amount_due") or 0),
        amount_paid_cents=int(obj.get("amount_paid") or 0),
        currency=str(obj.get("currency") or "usd"),
        hosted_invoice_url=obj.get("hosted_invoice_url"),
        invoice_pdf_url=obj.get("invoice_pdf"),
        due_at=obj.get("due_date"),
        paid_at=obj.get("status_transitions", {}).get("paid_at")
        if isinstance(obj.get("status_transitions"), dict)
        else None,
    )

    # Drive the subscription state machine off invoice events.
    sub_id = obj.get("subscription")
    if sub_id:
        sub = await billing_service.get_subscription_by_stripe_id(
            session, str(sub_id)
        )
        if sub is not None:
            event_type = event.get("type")
            if event_type == "invoice.paid":
                await billing_service.transition_status(
                    session, sub, to_status=SubscriptionStatus.ACTIVE, strict=False
                )
            elif event_type in {
                "invoice.payment_failed",
                "invoice.payment_action_required",
            }:
                await billing_service.transition_status(
                    session, sub, to_status=SubscriptionStatus.PAST_DUE, strict=False
                )


async def _handle_customer_updated(
    session: AsyncSession, event: dict[str, Any]
) -> None:
    obj = _data_object(event)
    customer_id = obj.get("id")
    if not customer_id:
        return
    cust = await billing_service.get_customer_by_stripe_id(session, str(customer_id))
    if cust is None:
        return
    email = obj.get("email")
    if email and email != cust.email_billing:
        cust.email_billing = email
        await session.flush()


HandlerFn = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


_DISPATCH: dict[str, HandlerFn] = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.created": _handle_subscription_event,
    "customer.subscription.updated": _handle_subscription_event,
    "customer.subscription.deleted": _handle_subscription_event,
    "invoice.created": _handle_invoice_event,
    "invoice.finalized": _handle_invoice_event,
    "invoice.paid": _handle_invoice_event,
    "invoice.payment_failed": _handle_invoice_event,
    "invoice.payment_action_required": _handle_invoice_event,
    "customer.updated": _handle_customer_updated,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def process_webhook(
    session: AsyncSession, *, payload: bytes, sig_header: str
) -> WebhookResult:
    """Verify + idempotently process a single Stripe webhook delivery."""

    event = verify_signature(payload=payload, sig_header=sig_header)
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        raise StripeSignatureError("event missing id/type")

    ledger, created = await claim_event(
        session,
        stripe_event_id=event_id,
        event_type=event_type,
        payload=event,
    )
    if not created:
        return WebhookResult(status="already_processed", event_id=event_id)

    handler = _DISPATCH.get(event_type)
    if handler is None:
        # Unknown but stored — Stripe still expects 200, otherwise it retries.
        await mark_processed(session, ledger)
        return WebhookResult(status="ignored", event_id=event_id)

    try:
        await handler(session, event)
        await mark_processed(session, ledger)
        return WebhookResult(status="processed", event_id=event_id)
    except Exception as exc:
        _logger.exception(
            "billing.webhook.handler_failed",
            event_id=event_id,
            event_type=event_type,
        )
        await mark_failed(session, ledger, str(exc))
        raise
