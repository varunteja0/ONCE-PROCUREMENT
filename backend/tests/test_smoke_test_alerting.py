from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import app.workers.tasks.smoke_test_tasks as smoke_tasks


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raise_on_call: int | None = None
        self._call_count = 0

    def notify(self, **kwargs: Any) -> bool:
        self._call_count += 1
        if self.raise_on_call is not None and self._call_count == self.raise_on_call:
            raise RuntimeError("simulated slack outage")
        self.calls.append(kwargs)
        return True


@pytest.fixture
def fake_notifier(monkeypatch: pytest.MonkeyPatch) -> _FakeNotifier:
    n = _FakeNotifier()
    monkeypatch.setattr(
        "app.workers.tasks.smoke_test_tasks.get_default_notifier", lambda: n
    )
    return n


@pytest.fixture
def state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "smoke_state.json"
    monkeypatch.setattr(
        "app.workers.tasks.smoke_test_tasks.settings.portal_smoke_state_path",
        str(p),
    )
    return p


def _result(platform: str, *, passed: bool, error: str | None = None) -> dict[str, Any]:
    return {
        "platform": platform,
        "submitter": f"{platform.title()}Submitter",
        "passed": passed,
        "error": error,
        "duration_sec": 1.0,
    }


def test_dispatch_alerts_emits_drift_on_first_failure(
    fake_notifier: _FakeNotifier, state_path: Path
) -> None:
    counts = smoke_tasks._dispatch_alerts(
        [_result("amtrust", passed=False, error="e")]
    )
    assert counts["drift"] == 1
    assert len(fake_notifier.calls) == 1
    call = fake_notifier.calls[0]
    assert call["severity"] == "critical"
    assert "DRIFT" in call["title"]


def test_dispatch_alerts_emits_recovery_after_fail(
    fake_notifier: _FakeNotifier, state_path: Path
) -> None:
    smoke_tasks._dispatch_alerts([_result("amtrust", passed=False, error="e")])
    smoke_tasks._dispatch_alerts([_result("amtrust", passed=True)])
    assert len(fake_notifier.calls) == 2
    assert fake_notifier.calls[1]["severity"] == "info"


def test_dispatch_alerts_emits_persistent_after_cooldown(
    fake_notifier: _FakeNotifier,
    state_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.workers.tasks.smoke_test_tasks.settings.portal_smoke_test_alert_cooldown_sec",
        0,
    )
    smoke_tasks._dispatch_alerts([_result("amtrust", passed=False, error="e")])
    smoke_tasks._dispatch_alerts([_result("amtrust", passed=False, error="e")])
    assert len(fake_notifier.calls) == 2
    assert fake_notifier.calls[1]["severity"] == "warning"


def test_dispatch_alerts_passes_emit_no_notify(
    fake_notifier: _FakeNotifier, state_path: Path
) -> None:
    counts = smoke_tasks._dispatch_alerts([_result("amtrust", passed=True)])
    assert counts["noop"] == 1
    assert fake_notifier.calls == []


def test_dispatch_alerts_handles_multiple_portals(
    fake_notifier: _FakeNotifier, state_path: Path
) -> None:
    # Seed: p1 fail (will recover on next call).
    smoke_tasks._dispatch_alerts([_result("p1", passed=False, error="e")])
    fake_notifier.calls.clear()

    results = [
        _result("p1", passed=True),               # recovery
        _result("p2", passed=False, error="e"),   # drift
        _result("p3", passed=False, error="e"),   # drift
        _result("p4", passed=True),               # noop
        _result("p5", passed=True),               # noop
    ]
    counts = smoke_tasks._dispatch_alerts(results)
    assert counts["recovery"] == 1
    assert counts["drift"] == 2
    assert counts["noop"] == 2


def test_dispatch_alerts_continues_when_notifier_raises(
    fake_notifier: _FakeNotifier, state_path: Path
) -> None:
    fake_notifier.raise_on_call = 1
    results = [
        _result("p1", passed=False, error="e"),  # raises
        _result("p2", passed=False, error="e"),  # must still be processed
    ]
    counts = smoke_tasks._dispatch_alerts(results)
    assert counts["drift"] == 2
    # Second result still produced a successful notify call.
    assert any("p2" in c["title"] for c in fake_notifier.calls)
    # Dispatch-failure counter incremented for the first.
    assert counts.get("dispatch_failures", 0) >= 1
