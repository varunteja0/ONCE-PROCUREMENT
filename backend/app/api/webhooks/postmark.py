"""L3.9 — Postmark inbound webhook.

Mounted at ``/webhooks/postmark/inbound`` (no ``/v1`` prefix) so the
Postmark dashboard URL stays stable across API versions. Public — no
session cookie — secured by:

* HTTP Basic Auth (Postmark's recommended pattern): the dashboard sends
  ``Authorization: Basic <base64(user:secret)>`` and we verify the
  ``secret`` portion against ``settings.postmark_webhook_secret`` using
  constant-time compare.

Idempotency
-----------
The pipeline keys on Postmark's ``MessageID`` field. Duplicate
deliveries (Postmark retries on 5xx) return ``200 OK`` with
``duplicate=true`` so Postmark stops retrying.

Body size
---------
Payload is JSON containing base64-encoded attachments — typical max ~30
MiB. CSRF middleware already exempts ``/webhooks/`` (see
``DEFAULT_BYPASS_PREFIXES``); the body-size middleware exempts this path
when configured via ``SECURITY_BODY_BYPASS_PREFIXES`` env (see
``app.middleware.body_size``).
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.schemas.inbound import PostmarkInboundIn, WebhookAck
from app.services.inbound_email_service import (
    EmailTooLarge,
    InboundIngestError,
    ParsedAttachment,
    ParsedEmail,
    TenantNotFound,
    ingest,
)
from app.utils.logging import get_logger

__all__ = ["router"]


router = APIRouter(prefix="/webhooks/postmark", tags=["webhooks"])
_logger = get_logger(__name__)


def _verify_secret(authorization: str | None) -> bool:
    """Constant-time check of the Postmark BasicAuth secret."""

    expected = (settings.postmark_webhook_secret or "").strip()
    if not expected:
        # Webhook secret not configured — only allow in development.
        return settings.is_development
    if not authorization:
        return False
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(parts[1], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    # Postmark sends "<user>:<secret>"; user is informational only.
    _, _, presented = decoded.partition(":")
    return hmac.compare_digest(presented.strip(), expected)


def _parse_cc(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()]


def _decode_attachment(att: dict) -> ParsedAttachment | None:
    name = (att.get("Name") or "").strip() or "unnamed"
    content_b64 = att.get("Content") or ""
    if not content_b64:
        return None
    try:
        content = base64.b64decode(content_b64, validate=False)
    except (binascii.Error, ValueError):
        return None
    return ParsedAttachment(
        filename=name,
        content_type=att.get("ContentType"),
        content=content,
    )


@router.post(
    "/inbound",
    response_model=WebhookAck,
    summary="Postmark inbound webhook (BasicAuth-signed; idempotent)",
)
async def receive_postmark_inbound(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> WebhookAck:
    body = await request.body()
    # Enforce a hard 30 MiB cap independent of the framework body limit
    # so a misconfigured middleware can't expose us to OOM via giant payloads.
    max_bytes = int(settings.inbound_max_email_size_mb) * 1024 * 1024
    if len(body) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="payload_too_large",
        )

    if not _verify_secret(authorization):
        _logger.warning("inbound.postmark_bad_auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_signature",
        )

    try:
        payload_dict = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_json",
        ) from exc

    try:
        payload = PostmarkInboundIn.model_validate(payload_dict)
    except Exception as exc:
        _logger.warning("inbound.postmark_invalid_payload", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_payload", "message": str(exc)[:512]},
        ) from exc

    attachments: list[ParsedAttachment] = []
    if payload.Attachments:
        for raw_att in payload.Attachments:
            decoded = _decode_attachment(raw_att.model_dump())
            if decoded is not None:
                attachments.append(decoded)

    headers_dict: dict[str, object] = {}
    if payload.Headers:
        for h in payload.Headers:
            name = h.get("Name") if isinstance(h, dict) else None
            value = h.get("Value") if isinstance(h, dict) else None
            if name:
                headers_dict[str(name)] = value

    parsed = ParsedEmail(
        message_id=payload.MessageID,
        from_address=payload.From,
        from_name=payload.FromName,
        to_address=payload.OriginalRecipient or payload.To,
        cc_addresses=_parse_cc(payload.Cc),
        subject=payload.Subject,
        text_body=payload.TextBody,
        html_body=payload.HtmlBody,
        in_reply_to=None,
        headers=headers_dict or None,
        attachments=attachments,
        raw_bytes=body,
    )

    try:
        email_row, duplicate = await ingest(session, parsed)
    except TenantNotFound as exc:
        # Don't 4xx the webhook on tenant-routing miss: log + 200 so
        # Postmark stops retrying. Operators inspect via logs.
        _logger.warning("inbound.postmark_tenant_not_found", error=str(exc))
        return WebhookAck(status="ignored_tenant_unknown", duplicate=False)
    except EmailTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "payload_too_large", "message": str(exc)},
        ) from exc
    except InboundIngestError as exc:
        _logger.warning("inbound.postmark_ingest_error", error=str(exc))
        # 200 anyway — webhook retries don't fix bad inputs.
        return WebhookAck(status="error", duplicate=False)

    return WebhookAck(
        status=email_row.status.value,
        email_id=email_row.id,
        duplicate=duplicate,
    )
