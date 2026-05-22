"""Phase 4 soak harness — stress-run each portal submitter against its local fixture.

Doubly gated: requires both ``RUN_INTEGRATION_TESTS=1`` (handled by
``backend/tests/integration/conftest.py``) and ``RUN_SOAK_TESTS=1`` (handled
locally below). Tuning knobs:

* ``SOAK_ITERATIONS`` (default ``25``) — runs per portal.
* ``SOAK_MIN_SUCCESS_RATIO`` (default ``0.95``) — failure threshold.
* ``SOAK_PER_RUN_TIMEOUT_SEC`` (default ``60``) — per-iteration wall-clock cap.

Run from ``backend/``::

    set RUN_INTEGRATION_TESTS=1
    set RUN_SOAK_TESTS=1
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_submitter_soak.py -s
"""
from __future__ import annotations

import asyncio
import os
import statistics
import time
from typing import Any

import pytest

from app.automation.submitters.amtrust import AmTrustSubmitter
from app.automation.submitters.applied_epic import AppliedEpicSubmitter
from app.automation.submitters.errors import PortalSelectorDriftError
from app.automation.submitters.markel import MarkelSubmitter
from app.automation.submitters.vertafore_ams360 import VertaforeAMS360Submitter

try:
    from app.automation.submitters.sircon import SirconSubmitter
except ImportError:  # pragma: no cover - parallel work-in-progress
    SirconSubmitter = None  # type: ignore[assignment,misc]


pytestmark = [
    pytest.mark.integration,
    pytest.mark.soak,
    pytest.mark.skipif(
        os.environ.get("RUN_SOAK_TESTS") != "1",
        reason="set RUN_SOAK_TESTS=1 to run soak suite",
    ),
]


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _iterations() -> int:
    return max(1, _int_env("SOAK_ITERATIONS", 25))


def _min_ratio() -> float:
    return _float_env("SOAK_MIN_SUCCESS_RATIO", 0.95)


def _per_run_timeout_sec() -> float:
    return _float_env("SOAK_PER_RUN_TIMEOUT_SEC", 60.0)


def _set_env(ep: Any, env_prefix: str) -> None:
    os.environ[f"PORTAL_{env_prefix}_URL"] = ep.base_url
    os.environ[f"{env_prefix}_USERNAME"] = ep.username
    os.environ[f"{env_prefix}_PASSWORD"] = ep.password
    os.environ.setdefault("PLAYWRIGHT_HEADLESS", "true")


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[idx]


_SIRCON_PARAM = (
    pytest.param(
        SirconSubmitter,
        "sircon_portal",
        "SIRCON",
        id="sircon",
    )
    if SirconSubmitter is not None
    else pytest.param(
        None,
        "sircon_portal",
        "SIRCON",
        id="sircon",
        marks=pytest.mark.skip(reason="SirconSubmitter not available yet"),
    )
)


@pytest.mark.parametrize(
    ("submitter_cls", "portal_fixture_name", "env_prefix"),
    [
        pytest.param(AmTrustSubmitter, "amtrust_portal", "AMTRUST", id="amtrust"),
        pytest.param(
            AppliedEpicSubmitter,
            "applied_epic_portal",
            "APPLIED_EPIC",
            id="applied_epic",
        ),
        pytest.param(MarkelSubmitter, "markel_portal", "MARKEL", id="markel"),
        pytest.param(
            VertaforeAMS360Submitter,
            "vertafore_portal",
            "VERTAFORE_AMS360",
            id="vertafore_ams360",
        ),
        _SIRCON_PARAM,
    ],
)
def test_portal_soak(
    request: pytest.FixtureRequest,
    submitter_cls: Any,
    portal_fixture_name: str,
    env_prefix: str,
    fake_supplier: Any,
    fake_portal: Any,
    base_payload: dict[str, Any],
) -> None:
    """Run ``SOAK_ITERATIONS`` back-to-back submissions; assert success ratio."""

    ep = request.getfixturevalue(portal_fixture_name)
    _set_env(ep, env_prefix)

    iterations = _iterations()
    min_ratio = _min_ratio()
    per_run_timeout = _per_run_timeout_sec()

    successes = 0
    selector_drift_count = 0
    auth_error_count = 0
    validation_count = 0
    timeout_count = 0
    other_count = 0
    durations: list[float] = []

    from app.automation.submitters.errors import (
        PortalAuthError,
        PortalTimeoutError,
        PortalValidationError,
    )

    for i in range(iterations):
        payload = dict(base_payload)
        payload["submission_id"] = f"{base_payload['submission_id']}-soak-{i:04d}"

        started = time.monotonic()
        try:
            outcome = asyncio.run(
                asyncio.wait_for(
                    submitter_cls.submit(
                        supplier=fake_supplier,
                        portal=fake_portal,
                        payload=payload,
                        consent=None,
                    ),
                    timeout=per_run_timeout,
                )
            )
            elapsed = time.monotonic() - started
            durations.append(elapsed)
            if getattr(outcome, "success", False):
                successes += 1
            else:
                other_count += 1
        except PortalSelectorDriftError:
            durations.append(time.monotonic() - started)
            selector_drift_count += 1
        except PortalAuthError:
            durations.append(time.monotonic() - started)
            auth_error_count += 1
        except PortalValidationError:
            durations.append(time.monotonic() - started)
            validation_count += 1
        except (TimeoutError, PortalTimeoutError):
            durations.append(time.monotonic() - started)
            timeout_count += 1
        except Exception:  # noqa: BLE001 - bucketed for soak summary
            durations.append(time.monotonic() - started)
            other_count += 1

    success_ratio = successes / iterations
    mean_duration_sec = statistics.mean(durations) if durations else 0.0
    p95_duration_sec = _p95(durations)
    max_duration_sec = max(durations) if durations else 0.0

    counts = {
        "iterations": iterations,
        "successes": successes,
        "success_ratio": round(success_ratio, 4),
        "selector_drift": selector_drift_count,
        "auth_error": auth_error_count,
        "validation": validation_count,
        "timeout": timeout_count,
        "other": other_count,
    }
    timings = {
        "mean_sec": round(mean_duration_sec, 3),
        "p95_sec": round(p95_duration_sec, 3),
        "max_sec": round(max_duration_sec, 3),
    }

    print(
        f"\n[soak] {env_prefix} portal={ep.base_url} "
        f"counts={counts} timings={timings}"
    )

    assert selector_drift_count == 0, (
        f"selector drift detected during soak: counts={counts} timings={timings}"
    )
    assert success_ratio >= min_ratio, (
        f"success ratio {success_ratio:.3f} below threshold {min_ratio:.3f}: "
        f"counts={counts} timings={timings}"
    )
