"""L3.9 — Postmark webhook tests."""

from __future__ import annotations

import base64

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.webhooks.postmark import router as postmark_router
from app.config import settings
from app.models import Tenant
from app.services.inbound_attachment_storage import LocalInboundStorage, reset_storage_for_tests

pytestmark = pytest.mark.asyncio

WEBHOOK_PATH = "/webhooks/postmark/inbound"
SECRET = "wh-secret-1234567890"


@pytest_asyncio.fixture
async def webhook_client(_test_engine, tmp_path, monkeypatch) -> AsyncClient:
    monkeypatch.setattr(settings, "postmark_webhook_secret", SECRET)
    storage = LocalInboundStorage(base_path=str(tmp_path))
    reset_storage_for_tests(storage)
    app = FastAPI()
    app.include_router(postmark_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    reset_storage_for_tests(None)


@pytest_asyncio.fixture
async def seeded_tenant(async_session: AsyncSession) -> Tenant:
    t = Tenant(name="Acme", slug="acme", plan="pilot", is_active=True)
    async_session.add(t)
    await async_session.flush()
    t.inbound_secret_token = None
    await async_session.commit()
    return t


def _basic_header(secret: str = SECRET, user: str = "postmark") -> str:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return f"Basic {token}"


def _payload(message_id: str = "<a@x.com>", **overrides):
    base = {
        "MessageID": message_id,
        "From": "broker@brokers.com",
        "FromName": "Broker",
        "To": "submissions@acme.in.getonce.com",
        "Subject": "Quote request",
        "TextBody": "Hello",
        "HtmlBody": None,
        "Attachments": [],
    }
    base.update(overrides)
    return base


async def test_webhook_rejects_missing_auth(webhook_client, seeded_tenant):
    r = await webhook_client.post(WEBHOOK_PATH, json=_payload())
    assert r.status_code == 401


async def test_webhook_rejects_bad_secret(webhook_client, seeded_tenant):
    r = await webhook_client.post(WEBHOOK_PATH, json=_payload(), headers={"Authorization": _basic_header("wrong")})
    assert r.status_code == 401


async def test_webhook_accepts_valid_payload(webhook_client, seeded_tenant):
    r = await webhook_client.post(WEBHOOK_PATH, json=_payload(), headers={"Authorization": _basic_header()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email_id"]
    assert body["duplicate"] is False


async def test_webhook_idempotent_on_duplicate(webhook_client, seeded_tenant):
    headers = {"Authorization": _basic_header()}
    p = _payload(message_id="<dup-1@x.com>")
    r1 = await webhook_client.post(WEBHOOK_PATH, json=p, headers=headers)
    r2 = await webhook_client.post(WEBHOOK_PATH, json=p, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["duplicate"] is True
    assert r1.json()["email_id"] == r2.json()["email_id"]


async def test_webhook_malformed_json_400(webhook_client, seeded_tenant):
    r = await webhook_client.post(
        WEBHOOK_PATH,
        content=b"not-json",
        headers={"Authorization": _basic_header(), "Content-Type": "application/json"},
    )
    assert r.status_code == 400


async def test_webhook_invalid_payload_400(webhook_client, seeded_tenant):
    r = await webhook_client.post(WEBHOOK_PATH, json={"foo": "bar"}, headers={"Authorization": _basic_header()})
    assert r.status_code == 400


async def test_webhook_unknown_tenant_returns_200(webhook_client, seeded_tenant):
    p = _payload(To="submissions@unknown.in.getonce.com", message_id="<u1@x.com>")
    r = await webhook_client.post(WEBHOOK_PATH, json=p, headers={"Authorization": _basic_header()})
    assert r.status_code == 200
    assert r.json()["status"] == "ignored_tenant_unknown"


async def test_webhook_decodes_attachment(webhook_client, seeded_tenant):
    raw = b"PDF-CONTENT" * 50
    p = _payload(
        message_id="<att-1@x.com>",
        Attachments=[
            {
                "Name": "quote.pdf",
                "Content": base64.b64encode(raw).decode(),
                "ContentType": "application/pdf",
                "ContentLength": len(raw),
            }
        ],
    )
    r = await webhook_client.post(WEBHOOK_PATH, json=p, headers={"Authorization": _basic_header()})
    assert r.status_code == 200
    assert r.json()["email_id"]


async def test_webhook_attachment_size_413(webhook_client, seeded_tenant, monkeypatch):
    monkeypatch.setattr(settings, "inbound_max_attachment_size_mb", 0)
    raw = b"X" * 100
    p = _payload(
        message_id="<big-1@x.com>",
        Attachments=[{"Name": "x.pdf", "Content": base64.b64encode(raw).decode()}],
    )
    r = await webhook_client.post(WEBHOOK_PATH, json=p, headers={"Authorization": _basic_header()})
    assert r.status_code == 413


async def test_webhook_30mb_body_cap(webhook_client, seeded_tenant, monkeypatch):
    monkeypatch.setattr(settings, "inbound_max_email_size_mb", 1)
    body = b"{" + b" " * (2 * 1024 * 1024) + b"}"
    r = await webhook_client.post(
        WEBHOOK_PATH,
        content=body,
        headers={"Authorization": _basic_header(), "Content-Type": "application/json"},
    )
    assert r.status_code == 413


async def test_webhook_dev_mode_no_secret_allows(webhook_client, seeded_tenant, monkeypatch):
    monkeypatch.setattr(settings, "postmark_webhook_secret", None)
    monkeypatch.setattr(settings, "app_env", "development")
    r = await webhook_client.post(WEBHOOK_PATH, json=_payload(message_id="<dev@x>"))
    assert r.status_code == 200
