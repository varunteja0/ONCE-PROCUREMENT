"""Tests for the email dispatcher: outbox writes, Resend fallback,
template rendering."""

from __future__ import annotations

import email
from pathlib import Path

import httpx
import pytest

from app.config import settings
from app.services import email_dispatcher as ed

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    ed.reset_dispatcher_cache()
    yield
    ed.reset_dispatcher_cache()


async def test_outbox_writes_eml(tmp_path: Path) -> None:
    dispatcher = ed.OutboxEmailDispatcher(outbox_dir=tmp_path)
    await dispatcher.send(
        to="user@example.com",
        subject="hi",
        html="<p>hello</p>",
        text="hello",
    )
    files = list(tmp_path.glob("*.eml"))
    assert len(files) == 1
    msg = email.message_from_bytes(files[0].read_bytes())
    assert msg["To"] == "user@example.com"
    assert msg["Subject"] == "hi"
    body_parts = [
        part.get_payload(decode=True).decode()
        for part in msg.walk()
        if part.get_content_maintype() == "text"
    ]
    assert any("hello" in part for part in body_parts)


async def test_outbox_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "deeply" / "nested"
    dispatcher = ed.OutboxEmailDispatcher(outbox_dir=target)
    await dispatcher.send(
        to="a@b.com", subject="s", html="<p/>", text="t"
    )
    assert target.exists()


async def test_get_dispatcher_default_is_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "email_dispatcher", "outbox")
    monkeypatch.setattr(settings, "resend_api_key", None, raising=False)
    dispatcher = ed.get_email_dispatcher()
    assert isinstance(dispatcher, ed.OutboxEmailDispatcher)


async def test_get_dispatcher_missing_resend_key_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "email_dispatcher", "resend")
    monkeypatch.setattr(settings, "resend_api_key", None, raising=False)
    dispatcher = ed.get_email_dispatcher()
    assert isinstance(dispatcher, ed.OutboxEmailDispatcher)


async def test_resend_dispatcher_raises_without_key() -> None:
    with pytest.raises(ed.EmailDispatcherError):
        ed.ResendEmailDispatcher(api_key=None)


async def test_resend_dispatcher_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"id": "fake"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = ed.ResendEmailDispatcher(api_key="key_test", http_client=client)
        await dispatcher.send(
            to="dst@example.com",
            subject="s",
            html="<p/>",
            text="t",
        )
    assert "resend.com" in captured["url"]  # type: ignore[operator]
    assert "Bearer key_test" in captured["headers"]["authorization"]  # type: ignore[index]
    assert "dst@example.com" in captured["body"]  # type: ignore[operator]


async def test_resend_dispatcher_error_on_4xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = ed.ResendEmailDispatcher(api_key="k", http_client=client)
        with pytest.raises(ed.EmailDispatcherError):
            await dispatcher.send(
                to="a@b.com", subject="s", html="<p/>", text="t"
            )


async def test_render_verify_email_contains_code() -> None:
    subject, html, text = ed.render_verify_email(
        code="123456", ttl_minutes=15, company_name="Acme"
    )
    assert "123456" in subject
    assert "123456" in html
    assert "123456" in text
    assert "Acme" in html


async def test_render_welcome_email_contains_link() -> None:
    subject, html, text = ed.render_welcome_email(
        company_name="Acme", dashboard_url="https://example.com/dashboard"
    )
    assert "Welcome" in subject
    assert "https://example.com/dashboard" in html
    assert "https://example.com/dashboard" in text
