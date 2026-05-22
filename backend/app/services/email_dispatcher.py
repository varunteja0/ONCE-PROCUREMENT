"""L3.6 — Provider-agnostic email dispatcher.

Two implementations are exposed:

* :class:`OutboxEmailDispatcher` — writes each message to
  ``.once/outbox/<timestamp>-<uuid>.eml`` as RFC822, never touches the
  network. The default in development + tests.
* :class:`ResendEmailDispatcher` — posts to the Resend HTTP API.

The active dispatcher is resolved by :func:`get_email_dispatcher` based on
``EMAIL_DISPATCHER`` and ``RESEND_API_KEY``. The Resend implementation
fails closed (raises :class:`EmailDispatcherError`) if the API key is
missing; in that case callers may fall back to the outbox dispatcher.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from string import Template
from typing import Protocol

import httpx

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "EmailDispatcher",
    "EmailDispatcherError",
    "OutboxEmailDispatcher",
    "ResendEmailDispatcher",
    "get_email_dispatcher",
    "reset_dispatcher_cache",
    "render_verify_email",
    "render_welcome_email",
]


_logger = get_logger(__name__)


class EmailDispatcherError(RuntimeError):
    """Raised when an email cannot be dispatched."""


class EmailDispatcher(Protocol):
    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: str,
        headers: Mapping[str, str] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Templates (stdlib ``string.Template``)
# ---------------------------------------------------------------------------
#
# We avoid a Jinja2 dependency to keep the runtime footprint small.
# Templates live in ``backend/app/templates/emails/`` as paired ``.html``
# and ``.txt`` files. ``string.Template`` performs ``$key`` substitution
# only — no logic — which is exactly what an email needs and side-steps
# the Jinja2 sandbox/escaping minefield. HTML safety is guaranteed by
# caller (we control all interpolated values).

_TEMPLATES_DIR: Path = Path(__file__).resolve().parent.parent / "templates" / "emails"


def _load(name: str, suffix: str) -> Template:
    path = _TEMPLATES_DIR / f"{name}.{suffix}"
    if not path.exists():
        raise EmailDispatcherError(f"missing email template: {path}")
    return Template(path.read_text(encoding="utf-8"))


def _render(name: str, context: Mapping[str, str]) -> tuple[str, str]:
    """Return ``(html, text)`` for a template name."""

    html = _load(name, "html").safe_substitute(context)
    text = _load(name, "txt").safe_substitute(context)
    return html, text


def render_verify_email(*, code: str, ttl_minutes: int, company_name: str) -> tuple[str, str, str]:
    """Return ``(subject, html, text)`` for the verification email."""

    subject = f"Your Once verification code: {code}"
    html, text = _render(
        "verify",
        {
            "code": code,
            "ttl_minutes": str(ttl_minutes),
            "company_name": company_name,
        },
    )
    return subject, html, text


def render_welcome_email(*, company_name: str, dashboard_url: str) -> tuple[str, str, str]:
    subject = "Welcome to Once — one submission, many carriers."
    html, text = _render(
        "welcome",
        {"company_name": company_name, "dashboard_url": dashboard_url},
    )
    return subject, html, text


# ---------------------------------------------------------------------------
# Outbox (dev)
# ---------------------------------------------------------------------------


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename_part(value: str) -> str:
    return _FILENAME_SAFE_RE.sub("_", value).strip("_") or "x"


class OutboxEmailDispatcher:
    """Writes every message to ``<outbox_dir>/<ts>-<uuid>.eml``.

    The file is a real RFC822 message so any mail client can open it.
    """

    def __init__(self, outbox_dir: str | os.PathLike[str] | None = None) -> None:
        self._dir = Path(outbox_dir or settings.email_outbox_dir)

    @property
    def directory(self) -> Path:
        return self._dir

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        msg = EmailMessage()
        msg["From"] = settings.email_from_address
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = datetime.now(tz=UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["X-Once-Dispatcher"] = "outbox"
        if headers:
            for k, v in headers.items():
                if k.lower() in {"from", "to", "subject", "date"}:
                    continue
                msg[k] = v
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
        filename = f"{timestamp}-{uuid.uuid4().hex[:8]}-{_safe_filename_part(to)}.eml"
        path = self._dir / filename
        path.write_bytes(bytes(msg))
        _logger.info("email_outbox_written", to=to, subject=subject, path=str(path))


# ---------------------------------------------------------------------------
# Resend (prod)
# ---------------------------------------------------------------------------


_RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailDispatcher:
    """Posts emails to the Resend HTTP API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        key = api_key if api_key is not None else settings.resend_api_key
        if not key:
            raise EmailDispatcherError("RESEND_API_KEY is not configured")
        self._api_key = key
        self._timeout = timeout_seconds
        self._http_client = http_client

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        text: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "from": settings.email_from_address,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        if headers:
            payload["headers"] = dict(headers)

        auth_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async def _send_with(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(
                _RESEND_API_URL,
                json=payload,
                headers=auth_headers,
                timeout=self._timeout,
            )

        try:
            if self._http_client is not None:
                response = await _send_with(self._http_client)
            else:
                async with httpx.AsyncClient() as client:
                    response = await _send_with(client)
        except httpx.HTTPError as exc:
            raise EmailDispatcherError(f"resend transport error: {exc}") from exc

        if response.status_code >= 400:
            raise EmailDispatcherError(
                f"resend api returned {response.status_code}: {response.text[:200]}"
            )
        _logger.info("email_resend_sent", to=to, subject=subject, status=response.status_code)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_dispatcher_cache: EmailDispatcher | None = None


def reset_dispatcher_cache() -> None:
    """Reset the cached dispatcher (tests / settings changes)."""

    global _dispatcher_cache
    _dispatcher_cache = None


def get_email_dispatcher() -> EmailDispatcher:
    """Resolve the active dispatcher per current settings.

    * ``EMAIL_DISPATCHER=resend`` and a ``RESEND_API_KEY`` present →
      :class:`ResendEmailDispatcher`.
    * Otherwise → :class:`OutboxEmailDispatcher` (safe default).
    """

    global _dispatcher_cache
    if _dispatcher_cache is not None:
        return _dispatcher_cache

    if settings.email_dispatcher == "resend" and settings.resend_api_key:
        try:
            _dispatcher_cache = ResendEmailDispatcher()
        except EmailDispatcherError as exc:
            _logger.warning(
                "email_dispatcher_fallback_to_outbox", reason=str(exc)
            )
            _dispatcher_cache = OutboxEmailDispatcher()
    else:
        if settings.email_dispatcher == "resend":
            _logger.warning("email_dispatcher_resend_missing_key_using_outbox")
        _dispatcher_cache = OutboxEmailDispatcher()
    return _dispatcher_cache
