"""Pluggable screenshot storage for Playwright submitters.

Local filesystem implementation today; the :class:`ScreenshotStore` protocol is
S3 / R2-ready so we can swap to object storage without touching submitter code.

Default root: ``$SCREENSHOT_DIR`` or ``./.once/screenshots`` (per project, not
``/tmp`` — the runtime forbids ``/tmp`` writes). Files are laid out as::

    {root}/{tenant_id}/{submission_id}/{utc_iso_ts}-{slug}.png

so that operator drilldowns can locate every artifact for a given submission
attempt in O(1) and audits can prune by tenant.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.utils.logging import get_logger

__all__ = [
    "ScreenshotStore",
    "LocalScreenshotStore",
    "get_default_store",
]

_logger = get_logger(__name__)
_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_DEFAULT_ROOT = Path(os.environ.get("SCREENSHOT_DIR", ".once/screenshots")).resolve()


def _slug(value: str) -> str:
    cleaned = _SLUG_RE.sub("-", value).strip("-")
    return cleaned[:64] or "shot"


class ScreenshotStore(Protocol):
    """Minimal contract every screenshot backend must satisfy."""

    def save(
        self,
        *,
        tenant_id: str,
        submission_id: str,
        label: str,
        data: bytes,
    ) -> str:
        """Persist ``data`` (PNG bytes) and return a stable locator string."""


class LocalScreenshotStore:
    """Writes PNGs to the local filesystem under a per-tenant tree."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root: Path = Path(root).resolve() if root else _DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        *,
        tenant_id: str,
        submission_id: str,
        label: str,
        data: bytes,
    ) -> str:
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        directory = self.root / _slug(tenant_id) / _slug(submission_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{ts}-{_slug(label)}.png"
        path.write_bytes(data)
        _logger.info(
            "screenshot_saved",
            tenant_id=tenant_id,
            submission_id=submission_id,
            label=label,
            path=str(path),
            bytes=len(data),
        )
        return str(path)


_default_store: ScreenshotStore | None = None


def get_default_store() -> ScreenshotStore:
    """Return a process-wide cached :class:`LocalScreenshotStore`."""

    global _default_store
    if _default_store is None:
        _default_store = LocalScreenshotStore()
    return _default_store
