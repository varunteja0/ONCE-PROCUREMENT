"""L3.9 — IMAP client tests.

We don't spin up a real IMAP server here; instead we exercise the parser
+ poll-once-with-raw-messages path which the production poller funnels
through, and mock the imaplib calls for the connection-level tests.
"""

from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.services.inbound_attachment_storage import LocalInboundStorage, reset_storage_for_tests
from app.workers import imap_client

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — asyncio_mode=auto
# already promotes async test functions, and the mark would attach to sync
# tests in this file as well, raising PytestUnraisableExceptionWarning.


def _raw_eml(
    *,
    message_id: str = "<imap-1@x.com>",
    from_addr: str = "broker@brokers.com",
    to_addr: str = "submissions@acme.in.getonce.com",
    subject: str = "Quote",
    attachment: tuple[str, bytes] | None = None,
) -> bytes:
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content("plain body")
    if attachment is not None:
        name, content = attachment
        msg.add_attachment(content, maintype="application", subtype="pdf", filename=name)
    return msg.as_bytes()


@pytest.fixture(autouse=True)
def _storage(tmp_path):
    s = LocalInboundStorage(base_path=str(tmp_path))
    reset_storage_for_tests(s)
    yield s
    reset_storage_for_tests(None)


def test_build_parsed_from_eml_extracts_fields():
    raw = _raw_eml(subject="hello world")
    parsed = imap_client.build_parsed_from_eml(raw)
    assert parsed.message_id == "<imap-1@x.com>"
    assert "broker@brokers.com" in parsed.from_address
    assert parsed.subject == "hello world"
    assert parsed.text_body and "plain body" in parsed.text_body


def test_build_parsed_collects_attachments():
    raw = _raw_eml(attachment=("q.pdf", b"PDFDATA" * 20))
    parsed = imap_client.build_parsed_from_eml(raw)
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "q.pdf"
    assert parsed.attachments[0].content.startswith(b"PDFDATA")


async def test_poll_once_with_raw_messages_ingests(async_session: AsyncSession):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    t.inbound_secret_token = None
    await async_session.commit()
    raws = [_raw_eml(message_id="<i1@x>"), _raw_eml(message_id="<i2@x>")]
    counts = await imap_client.poll_once(raw_messages=raws)
    assert counts["fetched"] == 2
    assert counts["ingested"] == 2
    assert counts["errors"] == 0


async def test_poll_once_with_raw_messages_duplicates(async_session: AsyncSession):
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    t.inbound_secret_token = None
    await async_session.commit()
    raw = _raw_eml(message_id="<dup-imap-1@x>")
    counts = await imap_client.poll_once(raw_messages=[raw, raw])
    assert counts["ingested"] == 1
    assert counts["duplicate"] == 1


def test_fetch_unseen_uids_uses_search_filter():
    cfg = imap_client.ImapConfig(host="example", username="u", password="p")
    client = imap_client.ImapClient(cfg)
    fake = MagicMock()
    fake.uid.return_value = ("OK", [b"3 4 5"])
    client._imap = fake  # type: ignore[attr-defined]
    out = client.fetch_unseen_uids(last_uid=2)
    assert out == [3, 4, 5]
    args = fake.uid.call_args[0]
    assert "UID 3:*" in args


def test_fetch_message_handles_no_data():
    cfg = imap_client.ImapConfig(host="example", username="u", password="p")
    client = imap_client.ImapClient(cfg)
    fake = MagicMock()
    fake.uid.return_value = ("NO", None)
    client._imap = fake  # type: ignore[attr-defined]
    assert client.fetch_message(99) is None
