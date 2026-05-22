"""L3.9 — Provider-agnostic attachment storage.

The storage interface intentionally returns opaque ``storage_url`` strings
so callers never depend on the underlying provider. Today: local
filesystem under ``settings.inbound_storage_path``. Tomorrow: S3 / GCS
(swap ``LocalInboundStorage`` for ``S3InboundStorage`` — the contract
stays identical).

Filename safety
---------------
We **never** write user-supplied filenames to disk. The on-disk path is
derived from the email id + sha256 of the bytes + a sanitized extension
from an allowlist. The original filename is preserved on the DB row for
display only.

Antivirus contract
------------------
Every byte string handed to :meth:`LocalInboundStorage.put` is run
through :func:`app.services.av_scanner.enforce_clean` **before** any
bytes touch the filesystem. Infected payloads raise
:class:`~app.services.av_scanner.InfectedFileError` and are never
persisted; the caller (typically
:mod:`app.services.inbound_email_service`) decides whether to skip the
attachment, quarantine the parent email, or fail the request.

Scanner unavailability is gated by
``settings.av_fail_closed_on_scanner_error``: production blocks the
upload, dev/test logs a warning and writes the file. The scanner itself
runs as a sidecar process (clamd in compose / k8s) — see
``docker-compose.yml`` for the opt-in profile. The EICAR test string
(used by the integration tests in ``tests/test_inbound_av_integration.py``)
proves the wiring end-to-end without requiring a real virus signature.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import settings
from app.services.av_scanner import (
    AvScanner,
    InfectedFileError,
    ScannerError,
    enforce_clean,
    get_scanner,
)
from app.utils.logging import get_logger

__all__ = [
    "StoredAttachment",
    "AttachmentStorage",
    "LocalInboundStorage",
    "get_storage",
    "reset_storage_for_tests",
    "sanitize_extension",
    "ALLOWED_EXTENSIONS",
]


_logger = get_logger(__name__)


# Defence in depth: even with a real AV scanner inline (see module
# docstring), we still gate on a conservative extension allowlist so a
# bug in the scanner client never lets executables land on disk.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        "pdf",
        "csv",
        "xlsx",
        "xls",
        "doc",
        "docx",
        "eml",
        "txt",
        "png",
        "jpg",
        "jpeg",
    }
)

_SAFE_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


def sanitize_extension(filename: str) -> str:
    """Return an allowlisted lowercase extension, or ``"bin"`` if unsafe."""

    if not filename or "." not in filename:
        return "bin"
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    if not _SAFE_EXT_RE.match(ext):
        return "bin"
    if ext not in ALLOWED_EXTENSIONS:
        return "bin"
    return ext


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    storage_url: str
    sha256: str
    size_bytes: int


class AttachmentStorage(Protocol):
    def put(
        self, *, email_id: str, filename: str, content: bytes
    ) -> StoredAttachment: ...

    def put_raw_email(self, *, email_id: str, content: bytes) -> str: ...

    def read(self, storage_url: str) -> bytes: ...


class LocalInboundStorage:
    """Filesystem-backed implementation rooted at ``settings.inbound_storage_path``."""

    def __init__(
        self,
        base_path: str | None = None,
        *,
        scanner: AvScanner | None = None,
    ) -> None:
        self.base_path = Path(base_path or settings.inbound_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        # Resolve the scanner lazily on each ``put`` so that test hooks
        # which call ``reset_scanner_for_tests`` after constructing the
        # storage still take effect.
        self._scanner_override = scanner

    def _resolve_scanner(self) -> AvScanner:
        return self._scanner_override or get_scanner()

    def put(
        self, *, email_id: str, filename: str, content: bytes
    ) -> StoredAttachment:
        sha = hashlib.sha256(content).hexdigest()
        size = len(content)
        try:
            enforce_clean(
                content,
                hint_name=filename,
                fail_closed_on_error=settings.av_fail_closed_on_scanner_error,
                scanner=self._resolve_scanner(),
            )
        except InfectedFileError as exc:
            _logger.error(
                "inbound_attachment_infected",
                email_id=email_id,
                signature=exc.signature,
                scanner=exc.scanner,
                sha256=sha,
                size=size,
                hint_name=filename,
            )
            raise
        except ScannerError as exc:
            _logger.error(
                "inbound_attachment_av_unavailable",
                email_id=email_id,
                scanner=exc.scanner,
                detail=exc.detail,
                sha256=sha,
                size=size,
                hint_name=filename,
            )
            raise

        ext = sanitize_extension(filename)
        target_dir = self._email_dir(email_id)
        safe_name = f"{sha}.{ext}"
        target = target_dir / safe_name
        if not target.exists():
            with open(target, "wb") as fh:
                fh.write(content)
        return StoredAttachment(
            storage_url=f"file://{target.resolve().as_posix()}",
            sha256=sha,
            size_bytes=size,
        )

    def _email_dir(self, email_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", email_id)[:64]
        path = self.base_path / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def put_raw_email(self, *, email_id: str, content: bytes) -> str:
        target = self._email_dir(email_id) / "raw.eml"
        if not target.exists():
            with open(target, "wb") as fh:
                fh.write(content)
        return f"file://{target.resolve().as_posix()}"

    def read(self, storage_url: str) -> bytes:
        if not storage_url.startswith("file://"):
            raise ValueError(f"Unsupported storage scheme: {storage_url}")
        path = storage_url[len("file://") :]
        # Defense in depth: must live inside base_path.
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.base_path.resolve())
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("storage_url escapes inbound storage root") from exc
        with open(resolved, "rb") as fh:
            return fh.read()


_storage_singleton: AttachmentStorage | None = None


def get_storage() -> AttachmentStorage:
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = LocalInboundStorage()
    return _storage_singleton


def reset_storage_for_tests(storage: AttachmentStorage | None = None) -> None:
    """Test hook to inject a custom storage implementation."""

    global _storage_singleton
    _storage_singleton = storage


_ = os  # silence linters in alternate envs
