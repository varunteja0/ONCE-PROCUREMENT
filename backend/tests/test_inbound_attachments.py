"""L3.9 — Attachment handling tests."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.services import inbound_email_service as svc
from app.services.inbound_attachment_storage import (
    LocalInboundStorage,
    reset_storage_for_tests,
    sanitize_extension,
)

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — asyncio_mode=auto
# already promotes async test functions, and the mark would attach to sync
# tests in this file as well, raising PytestUnraisableExceptionWarning.


@pytest.fixture(autouse=True)
def _storage(tmp_path):
    s = LocalInboundStorage(base_path=str(tmp_path))
    reset_storage_for_tests(s)
    yield s
    reset_storage_for_tests(None)


def test_sanitize_extension_lowercases():
    assert sanitize_extension("FOO.PDF") == "pdf"


def test_sanitize_extension_strips_path_traversal():
    assert sanitize_extension("../etc/passwd") == "bin"


def test_local_storage_writes_and_reads(tmp_path):
    storage = LocalInboundStorage(base_path=str(tmp_path))
    payload = b"hello-pdf"
    out = storage.put(email_id="email-1", filename="quote.pdf", content=payload)
    assert out.sha256 == hashlib.sha256(payload).hexdigest()
    assert out.size_bytes == len(payload)
    assert storage.read(out.storage_url) == payload


def test_local_storage_idempotent_same_sha(tmp_path):
    storage = LocalInboundStorage(base_path=str(tmp_path))
    out1 = storage.put(email_id="email-1", filename="q.pdf", content=b"abc")
    out2 = storage.put(email_id="email-1", filename="q.pdf", content=b"abc")
    assert out1.storage_url == out2.storage_url


async def test_dedupe_within_email(async_session: AsyncSession):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    t.inbound_secret_token = None
    await async_session.commit()
    content = b"identical"
    parsed = svc.ParsedEmail(
        message_id="<dedupe-1@x>",
        from_address="a@b.com",
        to_address="submissions@acme.in.getonce.com",
        subject="dup",
        attachments=[
            svc.ParsedAttachment("a.pdf", "application/pdf", content),
            svc.ParsedAttachment("a-copy.pdf", "application/pdf", content),
        ],
    )
    email, _ = await svc.ingest(async_session, parsed)
    assert email.attachment_count == 1


async def test_content_type_sniffed_from_filename(async_session: AsyncSession):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    t.inbound_secret_token = None
    await async_session.commit()
    parsed = svc.ParsedEmail(
        message_id="<m1@x>",
        from_address="a@b.com",
        to_address="submissions@acme.in.getonce.com",
        subject="x",
        attachments=[svc.ParsedAttachment("foo.csv", None, b"a,b,c\n1,2,3")],
    )
    email, _ = await svc.ingest(async_session, parsed)
    assert email.attachment_count == 1
