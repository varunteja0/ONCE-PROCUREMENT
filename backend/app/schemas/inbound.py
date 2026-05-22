"""L3.9 — Pydantic schemas for inbound email API + Postmark webhook."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

__all__ = [
    "PostmarkAttachmentIn",
    "PostmarkInboundIn",
    "InboundAttachmentRead",
    "InboundEmailRead",
    "InboundEmailListItem",
    "InboundEmailDetail",
    "InboundRuleCreate",
    "InboundRuleUpdate",
    "InboundRuleRead",
    "InboundRuleReorder",
    "InboundRetryResponse",
    "WebhookAck",
]


class PostmarkAttachmentIn(BaseModel):
    Name: str
    Content: str = Field(default="", description="base64-encoded content")
    ContentType: str | None = None
    ContentLength: int | None = None
    ContentID: str | None = None

    model_config = ConfigDict(extra="allow")


class PostmarkInboundIn(BaseModel):
    """Subset of Postmark's inbound JSON payload we consume.

    Postmark sends many more fields (e.g. ``MailboxHash``, ``StrippedTextReply``);
    we accept extras so the integration stays stable across Postmark
    payload revisions.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    MessageID: str
    From: str
    FromName: str | None = None
    To: str
    Cc: str | None = None
    Subject: str | None = None
    Date: str | None = None
    TextBody: str | None = None
    HtmlBody: str | None = None
    Headers: list[dict[str, Any]] | None = None
    Attachments: list[PostmarkAttachmentIn] | None = None
    OriginalRecipient: str | None = None
    MailboxHash: str | None = None


class InboundAttachmentRead(BaseModel):
    id: str
    filename: str
    content_type: str | None
    size_bytes: int
    sha256: str
    storage_url: str
    scanned_at: datetime | None = None


class InboundEmailRead(BaseModel):
    id: str
    tenant_id: str
    message_id: str
    from_address: str
    from_name: str | None
    to_address: str
    subject: str | None
    received_at: datetime
    status: str
    spam_score: float | None
    routing_error: str | None
    attachment_count: int
    draft_submission_id: str | None
    draft_supplier_id: str | None


class InboundEmailListItem(InboundEmailRead):
    pass


class InboundEmailDetail(InboundEmailRead):
    in_reply_to: str | None
    cc_addresses: list[str] | None
    raw_body_text: str | None
    raw_body_html: str | None
    headers: dict[str, Any] | None
    raw_storage_url: str | None
    attachments: list[InboundAttachmentRead]


class InboundRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    priority: int = Field(default=100, ge=0, le=999)
    match_from_domain: str | None = Field(default=None, max_length=255)
    match_subject_regex: str | None = Field(default=None, max_length=1024)
    match_attachment_kind: str | None = Field(default=None, max_length=64)
    action: Literal["create_submission", "quarantine", "discard", "tag_only"] = (
        "create_submission"
    )
    action_params: dict[str, Any] | None = None
    active: bool = True


class InboundRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    priority: int | None = Field(default=None, ge=0, le=999)
    match_from_domain: str | None = Field(default=None, max_length=255)
    match_subject_regex: str | None = Field(default=None, max_length=1024)
    match_attachment_kind: str | None = Field(default=None, max_length=64)
    action: Literal["create_submission", "quarantine", "discard", "tag_only"] | None = None
    action_params: dict[str, Any] | None = None
    active: bool | None = None


class InboundRuleRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    priority: int
    match_from_domain: str | None
    match_subject_regex: str | None
    match_attachment_kind: str | None
    action: str
    action_params: dict[str, Any] | None
    active: bool
    created_at: datetime


class InboundRuleReorder(BaseModel):
    order: list[str]


class InboundRetryResponse(BaseModel):
    id: str
    status: str
    routing_error: str | None


class WebhookAck(BaseModel):
    status: str
    email_id: str | None = None
    duplicate: bool = False


# Silence unused import warning for EmailStr (kept for future tightening).
_ = EmailStr
