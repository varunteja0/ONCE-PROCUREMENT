"""Per-portal smoke-test state tracker (Phase 4 drift detection).

The Celery beat task ``smoke_test.run_all`` writes a small JSON file after
every run so that the *next* run can distinguish three operationally distinct
situations:

1. ``PASS → FAIL``    — fresh drift; operator must be paged immediately.
2. ``FAIL → FAIL``    — still broken; emit a ``warning`` reminder every
                        ``cooldown_sec`` so the channel doesn't spam.
3. ``FAIL → PASS``    — recovery; emit an ``info`` ack with downtime metric.
4. ``PASS → PASS``    — no-op; nothing to say.

The state file is JSON shaped as::

    {
      "amtrust": {
        "last_status": "pass" | "fail",
        "last_changed_at": "<ISO-8601>",
        "last_alerted_at": "<ISO-8601> | null",
        "consecutive_failures": <int>
      },
      ...
    }

Storage is filesystem (no DB) because:

* the data is intentionally ephemeral (last-known-good per portal)
* it has no tenant scope (synthetic checks)
* SQLite-portable schema rule + L3 owns all current migration slots; adding
  a model + migration here would collide with the parallel L3 batch.

The tracker is process-local; in multi-worker Celery setups every worker
makes the same decision against the same shared file, which is fine because:

* The smoke-test beat task is singleton (``options.expires=600``).
* Writes are atomic (``os.replace`` on a temp file in the same directory).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.utils.logging import get_logger

__all__ = [
    "PortalRunStatus",
    "PortalStateSnapshot",
    "AlertDecision",
    "SmokeStateTracker",
]

_logger = get_logger(__name__)

PortalRunStatus = Literal["pass", "fail"]
AlertKind = Literal["drift", "persistent_failure", "recovery", "noop"]


@dataclass(frozen=True)
class PortalStateSnapshot:
    """Per-portal record persisted between smoke-test runs."""

    last_status: PortalRunStatus | None
    last_changed_at: datetime | None
    last_alerted_at: datetime | None
    consecutive_failures: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_status": self.last_status,
            "last_changed_at": _iso(self.last_changed_at),
            "last_alerted_at": _iso(self.last_alerted_at),
            "consecutive_failures": self.consecutive_failures,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PortalStateSnapshot:
        if not raw:
            return cls(
                last_status=None,
                last_changed_at=None,
                last_alerted_at=None,
                consecutive_failures=0,
            )
        return cls(
            last_status=raw.get("last_status"),
            last_changed_at=_parse_iso(raw.get("last_changed_at")),
            last_alerted_at=_parse_iso(raw.get("last_alerted_at")),
            consecutive_failures=int(raw.get("consecutive_failures") or 0),
        )


@dataclass(frozen=True)
class AlertDecision:
    """The verdict the tracker hands back after observing a new run."""

    kind: AlertKind
    """One of ``drift``, ``persistent_failure``, ``recovery``, ``noop``."""

    new_state: PortalStateSnapshot
    downtime_sec: float | None = None
    consecutive_failures: int = 0


class SmokeStateTracker:
    """JSON-file backed last-known-good map keyed by portal slug."""

    def __init__(
        self,
        *,
        state_path: str | os.PathLike[str],
        alert_cooldown_sec: int,
    ) -> None:
        self.state_path: Path = Path(state_path).resolve()
        self.alert_cooldown_sec: int = max(0, int(alert_cooldown_sec))

    # ---- public API --------------------------------------------------------

    def observe(
        self,
        *,
        platform: str,
        status: PortalRunStatus,
        now: datetime | None = None,
    ) -> AlertDecision:
        """Record a new run and return what (if anything) should be alerted."""

        now = now or datetime.now(UTC)
        state = self._load()
        prev = PortalStateSnapshot.from_dict(state.get(platform))

        decision = self._decide(prev=prev, status=status, now=now)
        state[platform] = decision.new_state.to_dict()
        self._save(state)
        return decision

    # ---- decision logic ----------------------------------------------------

    def _decide(
        self,
        *,
        prev: PortalStateSnapshot,
        status: PortalRunStatus,
        now: datetime,
    ) -> AlertDecision:
        # Case 1 — first observation ever.
        if prev.last_status is None:
            if status == "fail":
                return AlertDecision(
                    kind="drift",
                    consecutive_failures=1,
                    new_state=PortalStateSnapshot(
                        last_status="fail",
                        last_changed_at=now,
                        last_alerted_at=now,
                        consecutive_failures=1,
                    ),
                )
            return AlertDecision(
                kind="noop",
                consecutive_failures=0,
                new_state=PortalStateSnapshot(
                    last_status="pass",
                    last_changed_at=now,
                    last_alerted_at=None,
                    consecutive_failures=0,
                ),
            )

        # Case 2 — PASS → FAIL: fresh drift.
        if prev.last_status == "pass" and status == "fail":
            return AlertDecision(
                kind="drift",
                consecutive_failures=1,
                new_state=PortalStateSnapshot(
                    last_status="fail",
                    last_changed_at=now,
                    last_alerted_at=now,
                    consecutive_failures=1,
                ),
            )

        # Case 3 — FAIL → PASS: recovery.
        if prev.last_status == "fail" and status == "pass":
            downtime = (
                (now - prev.last_changed_at).total_seconds()
                if prev.last_changed_at is not None
                else None
            )
            return AlertDecision(
                kind="recovery",
                downtime_sec=downtime,
                consecutive_failures=0,
                new_state=PortalStateSnapshot(
                    last_status="pass",
                    last_changed_at=now,
                    last_alerted_at=now,
                    consecutive_failures=0,
                ),
            )

        # Case 4 — FAIL → FAIL: persistent failure (maybe re-alert).
        if prev.last_status == "fail" and status == "fail":
            new_count = prev.consecutive_failures + 1
            if prev.last_alerted_at is None:
                eligible = True
            else:
                elapsed = (now - prev.last_alerted_at).total_seconds()
                eligible = elapsed >= self.alert_cooldown_sec
            if eligible:
                return AlertDecision(
                    kind="persistent_failure",
                    consecutive_failures=new_count,
                    new_state=PortalStateSnapshot(
                        last_status="fail",
                        last_changed_at=prev.last_changed_at or now,
                        last_alerted_at=now,
                        consecutive_failures=new_count,
                    ),
                )
            return AlertDecision(
                kind="noop",
                consecutive_failures=new_count,
                new_state=PortalStateSnapshot(
                    last_status="fail",
                    last_changed_at=prev.last_changed_at or now,
                    last_alerted_at=prev.last_alerted_at,
                    consecutive_failures=new_count,
                ),
            )

        # Case 5 — PASS → PASS: silence.
        return AlertDecision(
            kind="noop",
            consecutive_failures=0,
            new_state=PortalStateSnapshot(
                last_status="pass",
                last_changed_at=prev.last_changed_at or now,
                last_alerted_at=prev.last_alerted_at,
                consecutive_failures=0,
            ),
        )

    # ---- persistence -------------------------------------------------------

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.state_path.exists():
            return {}
        try:
            raw = self.state_path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                _logger.warning(
                    "smoke_state_invalid_shape",
                    path=str(self.state_path),
                )
                return {}
            return data
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning(
                "smoke_state_load_failed",
                path=str(self.state_path),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return {}

    def _save(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp file + os.replace in the same directory.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".smoke_state.", suffix=".json", dir=str(self.state_path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, self.state_path)
        except OSError as exc:
            _logger.warning(
                "smoke_state_save_failed",
                path=str(self.state_path),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
