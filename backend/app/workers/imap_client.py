"""L3.9 — IMAP polling client (stdlib only).

Used in dev / fallback when a Postmark-style webhook isn't available
(self-hosted POPs, brokers who insist on forwarding to a real mailbox,
local debugging via maildev).

CLI usage::

    python -m app.workers.imap_client --once

The poll loop is intentionally simple: track the highest seen UID per
folder in a JSON file so re-runs are idempotent.
"""

from __future__ import annotations

import argparse
import asyncio
import email
import email.policy
import imaplib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from app.config import settings
from app.services.inbound_email_service import (
    InboundIngestError,
    ParsedAttachment,
    ParsedEmail,
    ingest,
)
from app.utils.logging import get_logger

__all__ = [
    "ImapConfig",
    "ImapClient",
    "build_parsed_from_eml",
    "poll_once",
    "main",
]


_logger = get_logger(__name__)


@dataclass(slots=True)
class ImapConfig:
    host: str
    port: int = 993
    username: str = ""
    password: str = ""
    folder: str = "INBOX"
    use_ssl: bool = True
    state_path: str = ".once/inbound/imap_state.json"


def _config_from_settings() -> ImapConfig | None:
    if not settings.imap_host or not settings.imap_username:
        return None
    return ImapConfig(
        host=settings.imap_host or "",
        port=int(settings.imap_port or 993),
        username=settings.imap_username or "",
        password=settings.imap_password or "",
        folder=settings.imap_folder or "INBOX",
        use_ssl=int(settings.imap_port or 993) == 993,
        state_path=os.path.join(settings.inbound_storage_path, "imap_state.json"),
    )


# ---------------------------------------------------------------------------
# State (UID tracking)
# ---------------------------------------------------------------------------


def _load_state(path: str) -> dict[str, int]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(path: str, state: dict[str, int]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state), "utf-8")


# ---------------------------------------------------------------------------
# IMAP wrapper
# ---------------------------------------------------------------------------


class ImapClient:
    """Thin wrapper around :class:`imaplib.IMAP4` / ``IMAP4_SSL``.

    Connection is opened lazily so tests can instantiate the class without
    network. ``fetch_unseen_uids`` returns UIDs strictly greater than the
    last-seen UID, enabling idempotent polling.
    """

    def __init__(self, config: ImapConfig) -> None:
        self.config = config
        self._imap: imaplib.IMAP4 | None = None

    def connect(self) -> imaplib.IMAP4:
        if self._imap is not None:
            return self._imap
        if self.config.use_ssl:
            self._imap = imaplib.IMAP4_SSL(self.config.host, self.config.port)
        else:
            self._imap = imaplib.IMAP4(self.config.host, self.config.port)
        self._imap.login(self.config.username, self.config.password)
        self._imap.select(self.config.folder)
        return self._imap

    def close(self) -> None:
        if self._imap is None:
            return
        try:
            self._imap.close()
        except Exception as exc:  # pragma: no cover - best-effort
            _logger.debug("imap.close_failed", error=str(exc))
        try:
            self._imap.logout()
        except Exception as exc:  # pragma: no cover
            _logger.debug("imap.logout_failed", error=str(exc))
        self._imap = None

    def fetch_unseen_uids(self, *, last_uid: int) -> list[int]:
        imap = self.connect()
        criterion = f"UID {last_uid + 1}:*" if last_uid > 0 else "ALL"
        typ, data = imap.uid("search", None, criterion)
        if typ != "OK" or not data or not data[0]:
            return []
        uids = [int(x) for x in data[0].split() if x.strip().isdigit()]
        return sorted(u for u in uids if u > last_uid)

    def fetch_message(self, uid: int) -> bytes | None:
        imap = self.connect()
        typ, data = imap.uid("fetch", str(uid), "(RFC822)")
        if typ != "OK" or not data:
            return None
        for chunk in data:
            if isinstance(chunk, tuple) and len(chunk) >= 2:
                return bytes(chunk[1])
        return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _extract_to(msg: EmailMessage) -> str:
    return str(msg.get("To") or msg.get("Delivered-To") or msg.get("X-Original-To") or "")


def _collect_attachments(msg: EmailMessage) -> list[ParsedAttachment]:
    out: list[ParsedAttachment] = []
    for part in msg.walk():
        disp = part.get_content_disposition()
        if disp not in {"attachment", "inline"}:
            continue
        if part.is_multipart():
            continue
        try:
            content = part.get_payload(decode=True) or b""
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("imap.attachment_decode_failed", error=str(exc))
            continue
        if not content:
            continue
        filename = part.get_filename() or "unnamed"
        ctype = part.get_content_type()
        out.append(ParsedAttachment(filename=filename, content_type=ctype, content=content))
    return out


def build_parsed_from_eml(raw: bytes) -> ParsedEmail:
    """Convert a raw RFC 5322 byte string into :class:`ParsedEmail`."""

    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)  # type: ignore[assignment]
    text_body = None
    html_body = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == "attachment":
                continue
            if ctype == "text/plain" and text_body is None:
                try:
                    text_body = part.get_content()
                except Exception:  # pragma: no cover
                    text_body = part.get_payload(decode=True).decode("utf-8", "replace")
            elif ctype == "text/html" and html_body is None:
                try:
                    html_body = part.get_content()
                except Exception:  # pragma: no cover
                    html_body = part.get_payload(decode=True).decode("utf-8", "replace")
    else:
        if msg.get_content_type() == "text/html":
            html_body = msg.get_content()
        else:
            try:
                text_body = msg.get_content()
            except Exception:
                text_body = msg.get_payload()

    headers = {k: v for k, v in msg.items()}

    cc_raw = msg.get("Cc") or ""
    cc = [c.strip() for c in cc_raw.split(",") if c.strip()] if cc_raw else None

    return ParsedEmail(
        message_id=(msg.get("Message-ID") or msg.get("Message-Id") or "").strip(),
        from_address=str(msg.get("From") or ""),
        from_name=None,
        to_address=_extract_to(msg),
        cc_addresses=cc,
        subject=str(msg.get("Subject") or "") or None,
        text_body=text_body if isinstance(text_body, str) else None,
        html_body=html_body if isinstance(html_body, str) else None,
        in_reply_to=msg.get("In-Reply-To"),
        headers=headers,
        attachments=_collect_attachments(msg),
        raw_bytes=raw,
    )


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------


async def poll_once(
    *,
    client: ImapClient | None = None,
    raw_messages: Iterable[bytes] | None = None,
) -> dict[str, int]:
    """Poll once and ingest new messages.

    Either provide an ``ImapClient`` (production) or an iterable of raw
    ``.eml`` byte payloads (tests).
    """


    counts = {"fetched": 0, "ingested": 0, "duplicate": 0, "errors": 0}

    if raw_messages is not None:
        for raw in raw_messages:
            counts["fetched"] += 1
            await _ingest_one(raw, counts)
        return counts

    if client is None:
        cfg = _config_from_settings()
        if cfg is None:
            _logger.info("inbound.imap_disabled")
            return counts
        client = ImapClient(cfg)

    state = _load_state(client.config.state_path)
    last_uid = int(state.get(client.config.folder, 0))
    try:
        uids = client.fetch_unseen_uids(last_uid=last_uid)
        for uid in uids:
            raw = client.fetch_message(uid)
            counts["fetched"] += 1
            if raw is None:
                counts["errors"] += 1
                continue
            await _ingest_one(raw, counts)
            state[client.config.folder] = uid
            _save_state(client.config.state_path, state)
    finally:
        client.close()

    return counts


async def _ingest_one(raw: bytes, counts: dict[str, int]) -> None:
    from app.db import AsyncSessionLocal

    parsed = build_parsed_from_eml(raw)
    if not parsed.message_id:
        counts["errors"] += 1
        _logger.warning("inbound.imap_missing_message_id")
        return
    async with AsyncSessionLocal() as session:
        try:
            _email, dup = await ingest(session, parsed)
            if dup:
                counts["duplicate"] += 1
            else:
                counts["ingested"] += 1
        except InboundIngestError as exc:
            counts["errors"] += 1
            _logger.warning("inbound.imap_ingest_error", error=str(exc))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="imap_client")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args(argv)

    if args.once:
        counts = asyncio.run(poll_once())
        print(json.dumps(counts))
        return 0

    parser.error("Only --once is currently supported")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
