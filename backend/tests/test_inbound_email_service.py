"""L3.9 — Inbound email service unit tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.inbound_email import InboundEmailStatus
from app.services import inbound_email_service as svc
from app.services.inbound_attachment_storage import (
    LocalInboundStorage,
    reset_storage_for_tests,
    sanitize_extension,
)

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — asyncio_mode=auto
# already promotes async test functions, and the mark would attach to sync
# tests in this file as well, raising PytestUnraisableExceptionWarning.


def _parsed(
    *,
    message_id: str = "<m1@example.com>",
    from_addr: str = "broker@brokers.com",
    to_addr: str = "submissions@acme.in.getonce.com",
    subject: str | None = "Quote request",
    attachments=None,
):
    return svc.ParsedEmail(
        message_id=message_id,
        from_address=from_addr,
        to_address=to_addr,
        subject=subject,
        text_body="Please find attached.",
        attachments=attachments or [],
    )


async def _seed_tenant(session: AsyncSession, slug: str = "acme") -> Tenant:
    t = Tenant(name="Acme", slug=slug, plan="pilot", is_active=True)
    session.add(t)
    await session.flush()
    return t


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    storage = LocalInboundStorage(base_path=str(tmp_path))
    reset_storage_for_tests(storage)
    yield storage
    reset_storage_for_tests(None)


def test_parse_to_address_subdomain():
    addr, slug = svc.parse_to_address("Submissions <submissions@acme.in.getonce.com>", inbound_domain="in.getonce.com")
    assert addr == "submissions@acme.in.getonce.com"
    assert slug == "acme"


def test_parse_to_address_local_part_only():
    addr, slug = svc.parse_to_address("acme@in.getonce.com", inbound_domain="in.getonce.com")
    assert slug == "acme"
    assert addr.endswith("@in.getonce.com")


def test_parse_to_address_strips_plus_tag():
    _, slug = svc.parse_to_address("acme+amtrust@in.getonce.com", inbound_domain="in.getonce.com")
    assert slug == "acme"


def test_parse_to_address_wrong_domain():
    with pytest.raises(svc.TenantNotFound):
        svc.parse_to_address("x@other.com", inbound_domain="in.getonce.com")


def test_sanitize_extension_allowlist():
    assert sanitize_extension("quote.pdf") == "pdf"
    assert sanitize_extension("rates.XLSX") == "xlsx"
    assert sanitize_extension("evil.exe") == "bin"
    assert sanitize_extension("noext") == "bin"
    assert sanitize_extension("../../etc/passwd") == "bin"


async def test_ingest_creates_email_and_routes(async_session: AsyncSession):
    await _seed_tenant(async_session)
    await async_session.commit()
    parsed = _parsed()
    email, dup = await svc.ingest(async_session, parsed)
    assert not dup
    assert email.status == InboundEmailStatus.ROUTED
    assert email.attachment_count == 0
    assert email.draft_supplier_id is None  # no supplier exists yet


async def test_ingest_is_idempotent_on_message_id(async_session: AsyncSession):
    await _seed_tenant(async_session)
    await async_session.commit()
    parsed = _parsed(message_id="<dup@example.com>")
    e1, dup1 = await svc.ingest(async_session, parsed)
    e2, dup2 = await svc.ingest(async_session, parsed)
    assert not dup1
    assert dup2
    assert e1.id == e2.id


async def test_ingest_unknown_tenant_raises(async_session: AsyncSession):
    with pytest.raises(svc.TenantNotFound):
        await svc.ingest(async_session, _parsed(to_addr="x@nope.in.getonce.com"))


async def test_ingest_stores_attachments_with_dedup(async_session: AsyncSession):
    await _seed_tenant(async_session)
    await async_session.commit()
    content = b"PDFCONTENT" * 100
    atts = [
        svc.ParsedAttachment("quote.pdf", "application/pdf", content),
        svc.ParsedAttachment("quote-copy.pdf", "application/pdf", content),
        svc.ParsedAttachment("rates.xlsx", None, b"different"),
    ]
    parsed = _parsed(attachments=atts)
    email, _ = await svc.ingest(async_session, parsed)
    # Same sha256 → dedup; 2 unique attachments stored.
    assert email.attachment_count == 2


async def test_ingest_disallowed_extension_dropped(async_session: AsyncSession):
    await _seed_tenant(async_session)
    await async_session.commit()
    atts = [svc.ParsedAttachment("hack.exe", "application/octet-stream", b"MZ")]
    parsed = _parsed(attachments=atts)
    email, _ = await svc.ingest(async_session, parsed)
    assert email.attachment_count == 0


async def test_attachment_size_limit_enforced(async_session: AsyncSession, monkeypatch):
    await _seed_tenant(async_session)
    await async_session.commit()
    from app.config import settings

    monkeypatch.setattr(settings, "inbound_max_attachment_size_mb", 0)  # 0 MiB → always too big
    atts = [svc.ParsedAttachment("quote.pdf", "application/pdf", b"X" * 100)]
    with pytest.raises(svc.EmailTooLarge):
        await svc.ingest(async_session, _parsed(attachments=atts))


async def test_spam_above_threshold_quarantines(async_session: AsyncSession):
    await _seed_tenant(async_session)
    await async_session.commit()
    parsed = _parsed(
        subject="LOTTERY WINNER click here now",
        from_addr="bot@spam.example",
    )
    parsed.headers = {"X-Spam-Flag": "YES"}
    email, _ = await svc.ingest(async_session, parsed)
    assert email.status == InboundEmailStatus.QUARANTINED
    assert (email.spam_score or 0) >= 0.9


async def test_retry_routing_changes_state(async_session: AsyncSession):
    tenant = await _seed_tenant(async_session)
    await async_session.commit()
    parsed = _parsed()
    email, _ = await svc.ingest(async_session, parsed)
    email.status = InboundEmailStatus.FAILED
    await async_session.flush()
    updated = await svc.retry_routing(async_session, tenant_id=tenant.id, email_id=email.id)
    assert updated.status == InboundEmailStatus.ROUTED
    _ = tenant


async def test_quarantine_action_sets_status(async_session: AsyncSession):
    tenant = await _seed_tenant(async_session)
    await async_session.commit()
    email, _ = await svc.ingest(async_session, _parsed())
    updated = await svc.quarantine(async_session, tenant_id=tenant.id, email_id=email.id)
    assert updated.status == InboundEmailStatus.QUARANTINED
