"""L3.9 — Inbound email orchestration service.

Single entry point for ingesting an email into the platform regardless of
source (Postmark webhook, IMAP poll). Responsibilities:

* Idempotency on ``message_id``.
* Tenant scoping by parsing the local-part of the ``To:`` address against
  ``settings.inbound_email_domain``.
* Attachment storage + per-attachment sha256 dedupe within the email.
* Spam scoring (quarantine above threshold).
* Routing-rule evaluation (priority asc; first match wins; fallback rule).
* Status transitions:
      received -> parsing -> routed | failed | quarantined

Designed for at-least-once delivery: ``ingest`` is safe to call multiple
times with the same ``message_id`` — it returns the existing row.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Tenant
from app.models.inbound_attachment import InboundAttachment
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.inbound_routing_rule import InboundRoutingRule, InboundRuleAction
from app.services.av_scanner import InfectedFileError, ScannerError
from app.services.inbound_attachment_storage import (
    AttachmentStorage,
    get_storage,
    sanitize_extension,
)
from app.services.inbound_routers import get_router
from app.services.spam_check import QUARANTINE_THRESHOLD, score_spam
from app.utils.logging import get_logger

__all__ = [
    "InboundIngestError",
    "TenantNotFound",
    "EmailTooLarge",
    "ParsedAttachment",
    "ParsedEmail",
    "ingest",
    "retry_routing",
    "parse_to_address",
]


_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InboundIngestError(Exception):
    """Base class for ingest errors."""


class TenantNotFound(InboundIngestError):
    pass


class EmailTooLarge(InboundIngestError):
    pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ParsedAttachment:
    filename: str
    content_type: str | None
    content: bytes


@dataclass(slots=True)
class ParsedEmail:
    message_id: str
    from_address: str
    to_address: str
    from_name: str | None = None
    cc_addresses: list[str] | None = None
    subject: str | None = None
    text_body: str | None = None
    html_body: str | None = None
    in_reply_to: str | None = None
    headers: dict[str, Any] | None = None
    attachments: list[ParsedAttachment] = None  # type: ignore[assignment]
    raw_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.attachments is None:
            self.attachments = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_EMAIL_RE = re.compile(r"<([^>]+)>|([^\s<>,]+@[^\s<>,]+)")


def _extract_address(raw: str) -> str:
    """Pull the first ``user@host`` token out of an RFC 5322-ish field."""

    if not raw:
        return ""
    raw = raw.strip()
    for m in _EMAIL_RE.finditer(raw):
        addr = (m.group(1) or m.group(2) or "").strip().lower()
        if addr and "@" in addr:
            return addr
    return raw.lower()


def parse_to_address(to_field: str, *, inbound_domain: str) -> tuple[str, str]:
    """Return ``(canonical_to_address, tenant_slug)``.

    Raises :class:`TenantNotFound` when the address local-part can't be
    mapped to a tenant slug under ``inbound_domain``.
    """

    address = _extract_address(to_field)
    if "@" not in address:
        raise TenantNotFound(f"Unparseable To: address: {to_field!r}")
    local, _, domain = address.partition("@")
    domain = domain.lower().strip()
    inbound_domain = inbound_domain.lower().strip()
    if not domain.endswith(inbound_domain):
        raise TenantNotFound(
            f"To: domain {domain!r} does not match inbound domain {inbound_domain!r}"
        )
    # local-part may look like "submissions+tag@<slug>.in.getonce.com" or
    # "submissions@<slug>.in.getonce.com" — derive slug from subdomain.
    sub = domain[: -len(inbound_domain)].rstrip(".")
    if not sub:
        # Catch-all: local-part is the slug, e.g. ``slug@in.getonce.com``.
        slug = local.split("+", 1)[0].strip()
    else:
        slug = sub.split(".")[0]
    if not slug:
        raise TenantNotFound(f"Could not derive tenant slug from {address!r}")
    return address, slug


async def _resolve_tenant(session: AsyncSession, slug: str) -> Tenant:
    stmt = select(Tenant).where(Tenant.slug == slug)
    tenant = (await session.execute(stmt)).scalar_one_or_none()
    if tenant is None:
        raise TenantNotFound(f"No tenant with slug {slug!r}")
    if not tenant.is_active:
        raise TenantNotFound(f"Tenant {slug!r} is inactive")
    return tenant


async def _existing_email(
    session: AsyncSession, *, message_id: str
) -> InboundEmail | None:
    stmt = select(InboundEmail).where(InboundEmail.message_id == message_id)
    return (await session.execute(stmt)).scalar_one_or_none()


def _enforce_size_limits(parsed: ParsedEmail) -> None:
    max_email = settings.inbound_max_email_size_mb * 1024 * 1024
    max_att = settings.inbound_max_attachment_size_mb * 1024 * 1024
    total = 0
    if parsed.raw_bytes:
        total += len(parsed.raw_bytes)
    for att in parsed.attachments:
        if len(att.content) > max_att:
            raise EmailTooLarge(
                f"Attachment {att.filename!r} exceeds "
                f"{settings.inbound_max_attachment_size_mb} MiB"
            )
        total += len(att.content)
    if total > max_email:
        raise EmailTooLarge(
            f"Email exceeds {settings.inbound_max_email_size_mb} MiB total"
        )


async def _store_attachments(
    *,
    storage: AttachmentStorage,
    email_id: str,
    attachments: Iterable[ParsedAttachment],
) -> list[InboundAttachment]:
    seen_sha: set[str] = set()
    rows: list[InboundAttachment] = []
    for att in attachments:
        ext = sanitize_extension(att.filename)
        if ext == "bin":
            _logger.warning(
                "inbound.attachment_disallowed_extension",
                filename=att.filename,
                email_id=email_id,
            )
            continue
        try:
            stored = storage.put(
                email_id=email_id, filename=att.filename, content=att.content
            )
        except InfectedFileError as exc:
            # Per-attachment failure — do NOT kill the whole email. The
            # storage layer has already emitted a structured
            # ``inbound_attachment_infected`` log line with sha + signature.
            _logger.warning(
                "inbound.attachment_quarantined",
                email_id=email_id,
                filename=att.filename,
                signature=exc.signature,
                scanner=exc.scanner,
            )
            continue
        except ScannerError as exc:
            # Fail-closed scanner downtime: drop the attachment and keep
            # the rest of the email moving. The storage layer logged the
            # structured ``inbound_attachment_av_unavailable`` event.
            _logger.warning(
                "inbound.attachment_skipped_av_unavailable",
                email_id=email_id,
                filename=att.filename,
                scanner=exc.scanner,
            )
            continue
        if stored.sha256 in seen_sha:
            # Dedupe within this email.
            continue
        seen_sha.add(stored.sha256)
        rows.append(
            InboundAttachment(
                inbound_email_id=email_id,
                filename=att.filename[:512],
                content_type=(att.content_type or "")[:255] or None,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                storage_url=stored.storage_url,
            )
        )
    return rows


async def _load_rules(
    session: AsyncSession, *, tenant_id: str
) -> list[InboundRoutingRule]:
    stmt = (
        select(InboundRoutingRule)
        .where(
            InboundRoutingRule.tenant_id == tenant_id,
            InboundRoutingRule.active.is_(True),
        )
        .order_by(InboundRoutingRule.priority.asc(), InboundRoutingRule.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


_FALLBACK_RULE_PRIORITY = 999


def _build_fallback_rule(tenant_id: str) -> InboundRoutingRule:
    return InboundRoutingRule(
        id="__fallback__",
        tenant_id=tenant_id,
        name="System fallback",
        priority=_FALLBACK_RULE_PRIORITY,
        match_from_domain=None,
        match_subject_regex=None,
        match_attachment_kind=None,
        action=InboundRuleAction.CREATE_SUBMISSION,
        action_params=None,
        active=True,
    )


def _attachment_kinds(attachments: list[InboundAttachment]) -> set[str]:
    kinds: set[str] = set()
    for a in attachments:
        ext = sanitize_extension(a.filename)
        if ext != "bin":
            kinds.add(ext)
    return kinds


def _rule_matches(
    rule: InboundRoutingRule,
    *,
    from_address: str,
    subject: str | None,
    attachment_kinds: set[str],
) -> bool:
    if rule.match_from_domain:
        domain = from_address.rsplit("@", 1)[-1].lower() if "@" in from_address else ""
        if domain != rule.match_from_domain.lower():
            return False
    if rule.match_subject_regex:
        try:
            if not re.search(rule.match_subject_regex, subject or "", re.IGNORECASE):
                return False
        except re.error:
            return False
    if rule.match_attachment_kind:
        if rule.match_attachment_kind.lower() not in attachment_kinds:
            return False
    return True


def select_rule(
    rules: list[InboundRoutingRule],
    *,
    tenant_id: str,
    from_address: str,
    subject: str | None,
    attachment_kinds: set[str],
) -> InboundRoutingRule:
    """Pick the first matching rule, falling back to the system default."""

    for rule in rules:
        if _rule_matches(
            rule,
            from_address=from_address,
            subject=subject,
            attachment_kinds=attachment_kinds,
        ):
            return rule
    return _build_fallback_rule(tenant_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ingest(
    session: AsyncSession,
    parsed: ParsedEmail,
    *,
    storage: AttachmentStorage | None = None,
) -> tuple[InboundEmail, bool]:
    """Persist + route an email. Returns ``(email_row, was_duplicate)``."""

    if not settings.inbound_email_enabled:
        raise InboundIngestError("Inbound email pipeline is disabled.")

    storage = storage or get_storage()

    existing = await _existing_email(session, message_id=parsed.message_id)
    if existing is not None:
        _logger.info(
            "inbound.duplicate_message_id",
            message_id=parsed.message_id,
            email_id=existing.id,
        )
        return existing, True

    _enforce_size_limits(parsed)

    to_address, slug = parse_to_address(
        parsed.to_address, inbound_domain=settings.inbound_email_domain
    )
    tenant = await _resolve_tenant(session, slug)

    spam_score = score_spam(
        from_address=parsed.from_address,
        subject=parsed.subject,
        body_text=parsed.text_body,
        headers=parsed.headers,
    )

    email = InboundEmail(
        tenant_id=tenant.id,
        message_id=parsed.message_id,
        in_reply_to=parsed.in_reply_to,
        from_address=parsed.from_address.lower(),
        from_name=parsed.from_name,
        to_address=to_address,
        cc_addresses=parsed.cc_addresses,
        subject=parsed.subject,
        received_at=datetime.now(UTC),
        raw_body_text=parsed.text_body,
        raw_body_html=parsed.html_body,
        headers=parsed.headers,
        spam_score=spam_score,
        status=InboundEmailStatus.PARSING,
        attachment_count=len(parsed.attachments),
    )
    session.add(email)
    try:
        await session.flush()
    except IntegrityError:
        # Concurrent duplicate insert; fall back to fetching the winner.
        await session.rollback()
        existing = await _existing_email(session, message_id=parsed.message_id)
        if existing is not None:
            return existing, True
        raise

    if parsed.raw_bytes:
        email.raw_storage_url = storage.put_raw_email(
            email_id=email.id, content=parsed.raw_bytes
        )

    att_rows = await _store_attachments(
        storage=storage, email_id=email.id, attachments=parsed.attachments
    )
    for row in att_rows:
        session.add(row)
    await session.flush()
    email.attachment_count = len(att_rows)

    # Auto-quarantine on high spam.
    if spam_score >= QUARANTINE_THRESHOLD:
        email.status = InboundEmailStatus.QUARANTINED
        email.routing_error = f"auto_quarantined: spam_score={spam_score}"
        await session.flush()
        await session.commit()
        return email, False

    await _route(session, email=email, attachments=att_rows)
    await session.commit()
    return email, False


async def _route(
    session: AsyncSession,
    *,
    email: InboundEmail,
    attachments: list[InboundAttachment],
) -> None:
    rules = await _load_rules(session, tenant_id=email.tenant_id)
    rule = select_rule(
        rules,
        tenant_id=email.tenant_id,
        from_address=email.from_address,
        subject=email.subject,
        attachment_kinds=_attachment_kinds(attachments),
    )
    router = get_router(rule.action)
    if router is None:
        email.status = InboundEmailStatus.FAILED
        email.routing_error = f"no_router_for_action:{rule.action.value}"
        await session.flush()
        return

    try:
        result = await router.route(
            session, email=email, attachments=attachments, rule=rule
        )
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("inbound.router_failed", email_id=email.id, error=str(exc))
        email.status = InboundEmailStatus.FAILED
        email.routing_error = f"{type(exc).__name__}: {exc}"[:2000]
        await session.flush()
        return

    if result.status == "quarantined":
        email.status = InboundEmailStatus.QUARANTINED
    elif result.status == "failed":
        email.status = InboundEmailStatus.FAILED
    else:
        email.status = InboundEmailStatus.ROUTED
    email.draft_submission_id = result.draft_submission_id
    email.draft_supplier_id = result.draft_supplier_id
    email.routing_error = result.error
    await session.flush()


async def retry_routing(
    session: AsyncSession, *, tenant_id: str, email_id: str
) -> InboundEmail:
    """Re-run routing for an existing email (operator action).

    ``tenant_id`` is required for defense-in-depth: a cross-tenant
    ``email_id`` raises :class:`InboundIngestError` instead of mutating
    another tenant's row.
    """

    if not tenant_id:
        raise InboundIngestError("tenant_id is required")
    stmt = select(InboundEmail).where(
        InboundEmail.id == email_id, InboundEmail.tenant_id == tenant_id
    )
    email = (await session.execute(stmt)).scalar_one_or_none()
    if email is None:
        raise InboundIngestError(f"InboundEmail {email_id!r} not found")
    att_stmt = select(InboundAttachment).where(
        InboundAttachment.inbound_email_id == email.id
    )
    attachments = list((await session.execute(att_stmt)).scalars().all())
    email.status = InboundEmailStatus.PARSING
    email.routing_error = None
    await _route(session, email=email, attachments=attachments)
    await session.commit()
    return email


async def quarantine(
    session: AsyncSession, *, tenant_id: str, email_id: str
) -> InboundEmail:
    """Mark *email_id* as quarantined.

    ``tenant_id`` is required: cross-tenant access raises
    :class:`InboundIngestError`.
    """

    if not tenant_id:
        raise InboundIngestError("tenant_id is required")
    stmt = select(InboundEmail).where(
        InboundEmail.id == email_id, InboundEmail.tenant_id == tenant_id
    )
    email = (await session.execute(stmt)).scalar_one_or_none()
    if email is None:
        raise InboundIngestError(f"InboundEmail {email_id!r} not found")
    email.status = InboundEmailStatus.QUARANTINED
    email.routing_error = "manual_quarantine"
    await session.flush()
    await session.commit()
    return email
