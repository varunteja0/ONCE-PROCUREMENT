"""Read-only portal-health snapshot service for the public coverage page.

The smoke-test beat task (``backend/app/workers/tasks/smoke_test_tasks.py``)
writes per-portal status into a JSON file via
:class:`app.automation.submitters._smoke_state.SmokeStateTracker`. This module
is the read side of that file: a stateless helper that returns a public,
non-tenant-scoped view of carrier coverage for the ``/v1/public/portals``
endpoint.

Design notes (CONTRACTS §10 / §12):

* No SQLAlchemy model, no DB query — the smoke-state store is intentionally
  a JSON file (see ``_smoke_state.py`` module docstring). Adding a model here
  would collide with the existing migration plan.
* No tenant scope — this is *carrier coverage*, not customer data. Equivalent
  to a public uptime page.
* Pure functions; safe to call from the request thread. File read is best
  effort: a missing or malformed state file is treated as "no observations
  yet" (every portal reported with ``status=unknown``) rather than 500-ing,
  because the public page must never depend on the worker being healthy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.automation.submitters import SUBMITTER_REGISTRY
from app.models.portal import PortalPlatform
from app.utils.logging import get_logger

__all__ = [
    "PortalCoverageRow",
    "PortalHealthStatus",
    "load_portal_coverage",
]

_logger = get_logger(__name__)

PortalHealthStatus = Literal["healthy", "degraded", "down", "unknown"]


# Human-readable carrier names for the public coverage page. Keyed by the
# ``PortalPlatform`` enum value (snake_case). Anything not in this map falls
# back to a title-cased version of the enum value.
_DISPLAY_NAMES: dict[PortalPlatform, str] = {
    PortalPlatform.APPLIED_EPIC: "Applied Epic",
    PortalPlatform.VERTAFORE_AMS360: "Vertafore AMS360",
    PortalPlatform.VERTAFORE_SIRCON: "Vertafore Sircon",
    PortalPlatform.AMTRUST: "AmTrust Financial",
    PortalPlatform.MARKEL: "Markel Specialty",
    PortalPlatform.NATIONWIDE_ES: "Nationwide E&S",
    PortalPlatform.CNA: "CNA",
    PortalPlatform.GUIDEWIRE: "Guidewire",
    PortalPlatform.HAWKSOFT: "HawkSoft",
    PortalPlatform.EZLYNX: "EZLynx",
    PortalPlatform.NOWCERTS: "NowCerts",
}


@dataclass(frozen=True)
class PortalCoverageRow:
    """Single row of the public carrier-coverage table."""

    platform: str
    """Stable machine identifier — ``PortalPlatform`` enum value."""

    display_name: str
    """Human-readable carrier / platform name."""

    supported: bool
    """``True`` if a concrete submitter is registered for this platform."""

    status: PortalHealthStatus
    """``healthy`` (last probe passed), ``degraded`` (1-2 recent failures),
    ``down`` (3+ consecutive failures), or ``unknown`` (no observations yet
    or platform not yet supported)."""

    last_status_change_at: datetime | None
    """When the status last flipped, if known."""

    consecutive_failures: int
    """0 when healthy; mirrors ``SmokeStateTracker``."""


def load_portal_coverage(
    *,
    state_path: str | Path,
) -> list[PortalCoverageRow]:
    """Return one ``PortalCoverageRow`` per declared :class:`PortalPlatform`.

    The list is stable across calls (sorted by display name) so cache layers
    and snapshot tests can rely on the ordering.
    """

    raw_state = _safe_read_state(Path(state_path))
    supported = set(SUBMITTER_REGISTRY.keys())

    rows: list[PortalCoverageRow] = []
    for platform in PortalPlatform:
        rows.append(
            _build_row(
                platform=platform,
                supported=platform in supported,
                raw=raw_state.get(platform.value),
            )
        )
    rows.sort(key=lambda r: r.display_name.lower())
    return rows


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _build_row(
    *,
    platform: PortalPlatform,
    supported: bool,
    raw: dict[str, object] | None,
) -> PortalCoverageRow:
    display = _DISPLAY_NAMES.get(platform, platform.value.replace("_", " ").title())

    if not supported:
        # Declared but not yet implemented — the public page shows these as
        # "roadmap" rather than hiding them, which is part of the GTM story.
        return PortalCoverageRow(
            platform=platform.value,
            display_name=display,
            supported=False,
            status="unknown",
            last_status_change_at=None,
            consecutive_failures=0,
        )

    if raw is None:
        return PortalCoverageRow(
            platform=platform.value,
            display_name=display,
            supported=True,
            status="unknown",
            last_status_change_at=None,
            consecutive_failures=0,
        )

    last_status = raw.get("last_status")
    consecutive = int(raw.get("consecutive_failures") or 0)  # type: ignore[call-overload]
    health = _derive_health(last_status=last_status, consecutive=consecutive)

    return PortalCoverageRow(
        platform=platform.value,
        display_name=display,
        supported=True,
        status=health,
        last_status_change_at=_parse_iso(raw.get("last_changed_at")),
        consecutive_failures=consecutive,
    )


def _derive_health(
    *,
    last_status: object,
    consecutive: int,
) -> PortalHealthStatus:
    if last_status == "pass":
        return "healthy"
    if last_status == "fail":
        if consecutive >= 3:
            return "down"
        return "degraded"
    return "unknown"


def _safe_read_state(path: Path) -> dict[str, dict[str, object]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        # Public coverage page must not depend on the worker subsystem; log
        # at warning level and degrade to "unknown" for every portal.
        _logger.warning("portal_health_state_unreadable", path=str(path), error=str(exc))
        return {}

    if not isinstance(data, dict):
        _logger.warning("portal_health_state_invalid_shape", path=str(path))
        return {}

    # Filter to dict-valued entries only (defensive against future schema
    # additions or hand-edits to the JSON file).
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
