"""Stripe webhook endpoint.

Mounted at ``/webhooks/stripe`` (no ``/v1`` prefix) so the URL we register
in the Stripe dashboard is stable across API revisions. Public — no auth
header — secured exclusively by HMAC signature.

Why this lives outside ``/v1``:

* Stripe webhook delivery does NOT carry cookies, so CSRF doesn't apply.
* The endpoint reads the **raw** request body (``await request.body()``)
  before any JSON parser touches it — ``Webhook.construct_event`` requires
  the original byte sequence to verify the HMAC.
* The default body-size limit (1 MiB) is well above Stripe's ~256 KB ceiling.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.billing import WebhookAck
from app.services.billing_webhooks import process_webhook
from app.services.stripe_client import StripeSignatureError
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/webhooks", tags=["webhooks"])
_logger = get_logger(__name__)


@router.post(
    "/stripe",
    response_model=WebhookAck,
    summary="Stripe webhook receiver (signed; idempotent)",
)
async def receive_stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookAck:
    body = await request.body()
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing_signature",
        )
    try:
        result = await process_webhook(session, payload=body, sig_header=stripe_signature)
    except StripeSignatureError as exc:
        _logger.warning("billing.webhook.bad_signature", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_signature",
        ) from exc
    return WebhookAck(status=result.status, event_id=result.event_id)  # type: ignore[arg-type]
