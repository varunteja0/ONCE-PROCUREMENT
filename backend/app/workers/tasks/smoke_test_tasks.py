from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from typing import Any

from app.automation.submitters._smoke_state import (
    AlertDecision,
    SmokeStateTracker,
)
from app.config import settings
from app.services.slack_notifier import (
    build_drift_payload,
    build_persistent_failure_payload,
    build_recovery_payload,
    get_default_notifier,
)
from app.utils.logging import get_logger
from app.workers.celery_app import celery_app

__all__ = ["run_all_smoke_tests"]


_logger = get_logger(__name__)


def _build_dry_instance(submitter_cls: type) -> Any:
    """Construct a submitter without invoking its full ``__init__``.

    Smoke tests must not require a real Supplier/Portal row; we bypass
    ``__init__`` with ``__new__`` and stub the four attributes the base
    class exposes (``supplier``, ``portal``, ``payload``, ``consent``).
    """

    instance = submitter_cls.__new__(submitter_cls)  # type: ignore[call-overload]
    instance.supplier = None
    instance.portal = None
    instance.payload = {}
    instance.consent = None
    return instance


async def _invoke_smoke(instance: Any, timeout: float) -> bool:
    method = getattr(instance, "_smoke_test", None)
    if method is None:
        return True
    result = method()
    if inspect.isawaitable(result):
        result = await asyncio.wait_for(result, timeout=timeout)
    return bool(result)


async def _run_all(timeout: float) -> list[dict[str, Any]]:
    try:
        from app.automation.submitters import SUBMITTER_REGISTRY
    except ImportError as exc:
        _logger.warning(
            "smoke_test_registry_unavailable",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return []

    results: list[dict[str, Any]] = []
    for platform, submitter_cls in SUBMITTER_REGISTRY.items():
        platform_value = getattr(platform, "value", str(platform))
        log = _logger.bind(platform=platform_value, submitter=submitter_cls.__name__)
        started = datetime.now(UTC)
        try:
            instance = _build_dry_instance(submitter_cls)
            passed = await _invoke_smoke(instance, timeout=timeout)
            entry: dict[str, Any] = {
                "platform": platform_value,
                "submitter": submitter_cls.__name__,
                "passed": passed,
                "error": None,
                "started_at": started.isoformat(),
                "duration_sec": (datetime.now(UTC) - started).total_seconds(),
            }
            if passed:
                log.info("smoke_test_passed")
            else:
                log.warning("smoke_test_failed_returned_false")
        except TimeoutError:
            log.warning("smoke_test_timeout", timeout_sec=timeout)
            entry = {
                "platform": platform_value,
                "submitter": submitter_cls.__name__,
                "passed": False,
                "error": f"timeout after {timeout}s",
                "started_at": started.isoformat(),
                "duration_sec": (datetime.now(UTC) - started).total_seconds(),
            }
        except Exception as exc:
            log.warning(
                "smoke_test_exception",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            entry = {
                "platform": platform_value,
                "submitter": submitter_cls.__name__,
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started.isoformat(),
                "duration_sec": (datetime.now(UTC) - started).total_seconds(),
            }
        results.append(entry)
    return results


@celery_app.task(
    bind=False,
    name="smoke_test.run_all",
    acks_late=True,
)
def run_all_smoke_tests() -> dict[str, Any]:
    """Run ``_smoke_test`` on every registered submitter and record results."""

    timeout = float(getattr(settings, "portal_smoke_test_timeout_sec", 60))
    started = datetime.now(UTC)
    _logger.info("smoke_tests_started", timeout_sec=timeout)

    try:
        results = asyncio.run(_run_all(timeout))
    except Exception as exc:
        _logger.exception(
            "smoke_tests_unhandled_error",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "results": [],
            "passed": 0,
            "failed": 0,
            "total": 0,
        }

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    finished = datetime.now(UTC)

    # Phase 4 — drift alerting: route each result through the state tracker
    # and dispatch the appropriate Slack message (drift / recovery / persistent).
    alert_counts = _dispatch_alerts(results)

    _logger.info(
        "smoke_tests_completed",
        total=len(results),
        passed=passed,
        failed=failed,
        duration_sec=(finished - started).total_seconds(),
        alerts=alert_counts,
    )

    return {
        "status": "ok",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
        "alerts": alert_counts,
    }


# ---------------------------------------------------------------------------
# Drift alerting
# ---------------------------------------------------------------------------


def _dispatch_alerts(results: list[dict[str, Any]]) -> dict[str, int]:
    """Feed each result through the state tracker; emit Slack on transitions."""

    tracker = SmokeStateTracker(
        state_path=settings.portal_smoke_state_path,
        alert_cooldown_sec=settings.portal_smoke_test_alert_cooldown_sec,
    )
    notifier = get_default_notifier()

    counts: dict[str, int] = {
        "drift": 0,
        "persistent_failure": 0,
        "recovery": 0,
        "noop": 0,
        "dispatch_failures": 0,
    }

    for result in results:
        platform: str = str(result.get("platform") or "unknown")
        submitter: str = str(result.get("submitter") or "")
        passed: bool = bool(result.get("passed"))
        duration: float = float(result.get("duration_sec") or 0.0)
        error: str | None = result.get("error")

        decision: AlertDecision = tracker.observe(
            platform=platform,
            status="pass" if passed else "fail",
        )
        counts[decision.kind] = counts.get(decision.kind, 0) + 1

        notify_kwargs: dict[str, Any] | None = None
        if decision.kind == "drift":
            notify_kwargs = build_drift_payload(
                platform=platform,
                error=error,
                submitter=submitter,
                duration_sec=duration,
            )
        elif decision.kind == "persistent_failure":
            notify_kwargs = build_persistent_failure_payload(
                platform=platform,
                error=error,
                submitter=submitter,
                consecutive_failures=decision.consecutive_failures,
                duration_sec=duration,
            )
        elif decision.kind == "recovery":
            notify_kwargs = build_recovery_payload(
                platform=platform,
                submitter=submitter,
                downtime_sec=decision.downtime_sec or 0.0,
            )

        if notify_kwargs is None:
            continue

        # Slack outages MUST NOT crash the beat task or stop subsequent alerts.
        try:
            notifier.notify(**notify_kwargs)
        except Exception as exc:  # noqa: BLE001 - all delivery errors swallowed
            counts["dispatch_failures"] = counts.get("dispatch_failures", 0) + 1
            _logger.warning(
                "smoke_alert_dispatch_error",
                platform=platform,
                kind=decision.kind,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    return counts
