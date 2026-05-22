from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.automation.submitters._smoke_state import SmokeStateTracker

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _tracker(tmp_path: Path, *, cooldown: int = 900) -> SmokeStateTracker:
    return SmokeStateTracker(
        state_path=tmp_path / "state.json", alert_cooldown_sec=cooldown
    )


def test_first_observation_pass_is_noop(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    d = t.observe(platform="amtrust", status="pass", now=T0)
    assert d.kind == "noop"
    data = json.loads((tmp_path / "state.json").read_text())
    assert data["amtrust"]["last_status"] == "pass"


def test_first_observation_fail_is_drift(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    d = t.observe(platform="amtrust", status="fail", now=T0)
    assert d.kind == "drift"
    assert d.consecutive_failures == 1


def test_pass_to_fail_is_drift(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    t.observe(platform="amtrust", status="pass", now=T0)
    d = t.observe(platform="amtrust", status="fail", now=T0 + timedelta(seconds=30))
    assert d.kind == "drift"
    assert d.consecutive_failures == 1


def test_fail_to_pass_is_recovery_with_downtime(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    t.observe(platform="amtrust", status="fail", now=T0)
    d = t.observe(platform="amtrust", status="pass", now=T0 + timedelta(seconds=60))
    assert d.kind == "recovery"
    assert d.downtime_sec == 60


def test_fail_to_fail_within_cooldown_is_noop(tmp_path: Path) -> None:
    t = _tracker(tmp_path, cooldown=900)
    t.observe(platform="amtrust", status="fail", now=T0)  # drift
    d = t.observe(
        platform="amtrust", status="fail", now=T0 + timedelta(seconds=100)
    )
    assert d.kind == "noop"
    assert d.consecutive_failures == 2


def test_fail_to_fail_after_cooldown_is_persistent(tmp_path: Path) -> None:
    t = _tracker(tmp_path, cooldown=900)
    t.observe(platform="amtrust", status="fail", now=T0)
    d = t.observe(
        platform="amtrust", status="fail", now=T0 + timedelta(seconds=901)
    )
    assert d.kind == "persistent_failure"
    assert d.consecutive_failures == 2


def test_pass_to_pass_is_noop(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    d1 = t.observe(platform="amtrust", status="pass", now=T0)
    d2 = t.observe(
        platform="amtrust", status="pass", now=T0 + timedelta(seconds=30)
    )
    assert d1.kind == "noop"
    assert d2.kind == "noop"


def test_state_persists_across_tracker_instances(tmp_path: Path) -> None:
    t1 = _tracker(tmp_path)
    t1.observe(platform="amtrust", status="fail", now=T0)
    t2 = _tracker(tmp_path)
    d = t2.observe(
        platform="amtrust", status="pass", now=T0 + timedelta(seconds=45)
    )
    assert d.kind == "recovery"
    assert d.downtime_sec == 45


def test_corrupt_state_file_is_treated_as_empty(tmp_path: Path) -> None:
    sp = tmp_path / "state.json"
    sp.write_text("not json")
    t = SmokeStateTracker(state_path=sp, alert_cooldown_sec=900)
    d = t.observe(platform="amtrust", status="pass", now=T0)
    assert d.kind == "noop"


def test_atomic_write_no_partial_file_on_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(src, dst):  # type: ignore[no-untyped-def]
        raise OSError("disk full")

    monkeypatch.setattr(
        "app.automation.submitters._smoke_state.os.replace", _boom
    )
    t = _tracker(tmp_path)
    t.observe(platform="amtrust", status="pass", now=T0)
    leftovers = list(tmp_path.glob(".smoke_state.*"))
    assert leftovers == []


def test_multiple_platforms_independent(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    d_am = t.observe(platform="amtrust", status="fail", now=T0)
    d_mk = t.observe(platform="markel", status="pass", now=T0)
    assert d_am.kind == "drift"
    assert d_mk.kind == "noop"
    data = json.loads((tmp_path / "state.json").read_text())
    assert "amtrust" in data
    assert "markel" in data


def test_observe_uses_default_now_when_none(tmp_path: Path) -> None:
    t = _tracker(tmp_path)
    d = t.observe(platform="amtrust", status="pass")
    assert d.kind == "noop"
    data = json.loads((tmp_path / "state.json").read_text())
    last_changed = data["amtrust"]["last_changed_at"]
    assert isinstance(last_changed, str)
    datetime.fromisoformat(last_changed)
