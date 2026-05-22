from __future__ import annotations

import csv
import io
import os
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.utils.logging import get_logger

__all__ = [
    "SanctionsCache",
    "SanctionsEntry",
    "OFAC_SDN_URL",
    "is_sanctioned",
    "refresh_ofac_sdn_list",
    "get_cache",
    "reset_cache",
]


_logger = get_logger(__name__)


OFAC_SDN_URL: str = "https://www.treasury.gov/ofac/downloads/sdn.csv"
"""Public OFAC Specially Designated Nationals list (CSV format)."""

_DEFAULT_CACHE_DIR: Path = Path(
    os.environ.get(
        "ONCE_SANCTIONS_CACHE_DIR",
        str(Path.home() / ".cache" / "once" / "sanctions"),
    )
)
_DEFAULT_CACHE_FILE: Path = _DEFAULT_CACHE_DIR / "ofac_sdn.csv"


@dataclass(frozen=True, slots=True)
class SanctionsEntry:
    """A single normalized record from a sanctions list."""

    source: str
    sdn_id: str
    name: str
    name_lower: str
    sdn_type: str
    program: str
    raw_ein: str | None = None


@dataclass(slots=True)
class SanctionsCache:
    """In-memory cache of normalized sanctions entries.

    The cache is process-local. The Celery beat task refreshes it every
    six hours; web/API requests then query :func:`is_sanctioned` in O(n)
    over the name set (a few thousand entries — fine for our scale).
    """

    entries: list[SanctionsEntry] = field(default_factory=list)
    names_lower: list[str] = field(default_factory=list)
    eins: set[str] = field(default_factory=set)
    loaded_at: datetime | None = None
    source_url: str | None = None
    source_path: str | None = None

    def is_empty(self) -> bool:
        return not self.entries

    def replace(self, entries: Iterable[SanctionsEntry], *, source_url: str | None,
                source_path: str | None) -> None:
        entries_list = list(entries)
        self.entries = entries_list
        self.names_lower = [e.name_lower for e in entries_list]
        self.eins = {e.raw_ein for e in entries_list if e.raw_ein}
        self.loaded_at = datetime.now(UTC)
        self.source_url = source_url
        self.source_path = source_path


_cache_lock = threading.Lock()
_cache: SanctionsCache = SanctionsCache()


def get_cache() -> SanctionsCache:
    """Return the process-local sanctions cache (never ``None``)."""

    return _cache


def reset_cache() -> None:
    """Clear the in-memory cache. Primarily intended for tests."""

    with _cache_lock:
        _cache.entries = []
        _cache.names_lower = []
        _cache.eins = set()
        _cache.loaded_at = None
        _cache.source_url = None
        _cache.source_path = None


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _digits_only(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _parse_sdn_csv(raw_bytes: bytes) -> list[SanctionsEntry]:
    """Parse an OFAC SDN CSV payload into normalized entries.

    The official SDN.csv has no header row and is documented as:
    ``ent_num, sdn_name, sdn_type, program, title, call_sign, vess_type,
    tonnage, grt, vess_flag, vess_owner, remarks``.
    """

    text = raw_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    entries: list[SanctionsEntry] = []
    for row in reader:
        if not row:
            continue
        sdn_id = (row[0] if len(row) > 0 else "").strip()
        name = (row[1] if len(row) > 1 else "").strip()
        sdn_type = (row[2] if len(row) > 2 else "").strip()
        program = (row[3] if len(row) > 3 else "").strip()
        remarks = (row[11] if len(row) > 11 else "").strip()
        if not name:
            continue
        entries.append(
            SanctionsEntry(
                source="OFAC_SDN",
                sdn_id=sdn_id,
                name=name,
                name_lower=_normalize_name(name),
                sdn_type=sdn_type,
                program=program,
                raw_ein=_digits_only(remarks) if "EIN" in remarks.upper() else None,
            )
        )
    return entries


def _load_from_disk(path: Path) -> bytes | None:
    try:
        if path.exists() and path.stat().st_size > 0:
            return path.read_bytes()
    except OSError as exc:  # pragma: no cover - defensive
        _logger.warning("sanctions_disk_read_failed", path=str(path), error=str(exc))
    return None


def _write_to_disk(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    except OSError as exc:  # pragma: no cover - defensive
        _logger.warning("sanctions_disk_write_failed", path=str(path), error=str(exc))


def _should_fetch_network() -> bool:
    """Block network access in test contexts to keep the suite hermetic."""

    if os.environ.get("APP_ENV", "").lower() == "test":
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if getattr(settings, "app_env", "") == "test":
        return False
    return True


def _download_sdn_csv(url: str, timeout: float = 30.0) -> bytes | None:
    """Download the SDN CSV. Returns ``None`` on any network failure."""

    try:  # pragma: no cover - exercised only in non-test envs
        import urllib.request
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            _logger.warning("sanctions_download_blocked_scheme", url=url)
            return None
        req = urllib.request.Request(url, headers={"User-Agent": "Once/1.0 (+sanctions)"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.read()
    except Exception as exc:  # pragma: no cover - network-dependent
        _logger.warning(
            "sanctions_download_failed", url=url, error=str(exc), error_type=type(exc).__name__
        )
        return None


def refresh_ofac_sdn_list(
    *,
    url: str = OFAC_SDN_URL,
    cache_file: Path | None = None,
) -> int:
    """Refresh the OFAC SDN cache. Returns the number of entries loaded.

    Resilient to network failure: on any error the existing on-disk cache
    (if any) is loaded and the in-memory cache is left untouched if no
    fallback is available. Returns ``0`` on total failure.

    In ``APP_ENV=test`` (or when running under pytest) the network call is
    skipped entirely; only the disk cache is consulted.
    """

    target_path = cache_file or _DEFAULT_CACHE_FILE
    log = _logger.bind(url=url, cache_file=str(target_path))

    payload: bytes | None = None
    if _should_fetch_network():
        payload = _download_sdn_csv(url)
        if payload is not None:
            _write_to_disk(target_path, payload)
            log.info("sanctions_download_succeeded", bytes=len(payload))
    else:
        log.info("sanctions_network_skipped_in_test_env")

    if payload is None:
        payload = _load_from_disk(target_path)
        if payload is None:
            log.info("sanctions_no_data_available", count=0)
            return 0
        log.info("sanctions_loaded_from_disk", bytes=len(payload))

    try:
        entries = _parse_sdn_csv(payload)
    except Exception as exc:
        log.exception("sanctions_parse_failed", error=str(exc))
        return 0

    with _cache_lock:
        _cache.replace(
            entries,
            source_url=url,
            source_path=str(target_path),
        )

    log.info("sanctions_cache_refreshed", count=len(entries))
    return len(entries)


def is_sanctioned(legal_name: str, ein: str | None = None) -> bool:
    """Return True if ``legal_name`` or ``ein`` matches a sanctioned party.

    * ``legal_name`` is matched case-insensitively as a substring.
    * ``ein`` is matched exactly on its digits-only normalization.

    If the cache is empty (never refreshed) this returns ``False`` rather
    than raising; the caller decides whether to treat unknown as block.
    """

    if not legal_name and not ein:
        return False

    cache = get_cache()
    if cache.is_empty():
        return False

    if ein:
        normalized_ein = _digits_only(ein)
        if normalized_ein and normalized_ein in cache.eins:
            return True

    if legal_name:
        needle = _normalize_name(legal_name)
        if needle:
            for name_lower in cache.names_lower:
                if needle in name_lower or name_lower in needle:
                    return True

    return False
