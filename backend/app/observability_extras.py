"""Prometheus metric definitions for the Once API.

This module is intentionally orthogonal to ``app.observability`` (which owns
Sentry and exception handlers). It defines the canonical metric inventory and
helpers used by middleware, services and Celery tasks.

All metrics are registered against ``prometheus_client.REGISTRY`` (the default
process registry) so the standard ``ProcessCollector`` and
``PlatformCollector`` light up automatically.

Cardinality discipline
----------------------
Labels are **bounded**: ``method`` (a small HTTP verb set), ``route`` (the
FastAPI route template, not the raw path — see ``route_template_of``), ``status``
(integer status code as string), ``portal`` (the small platform enum),
``state`` (Celery task state), ``key_id`` (signing key id — small N), ``result``
(login outcome enum). We never label by user_id, tenant_id, supplier_id or
arbitrary user input.
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)

# Re-export default registry so test code & metrics endpoint share it.
DEFAULT_REGISTRY: CollectorRegistry = REGISTRY


def _ensure_default_collectors() -> None:
    """Idempotently register process + platform collectors on the default registry."""

    names = {type(c).__name__ for c in list(REGISTRY._collector_to_names.keys())}  # type: ignore[attr-defined]
    if "ProcessCollector" not in names:
        try:
            ProcessCollector(registry=REGISTRY)
        except ValueError:  # pragma: no cover - already registered
            pass
    if "PlatformCollector" not in names:
        try:
            PlatformCollector(registry=REGISTRY)
        except ValueError:  # pragma: no cover - already registered
            pass


_ensure_default_collectors()


def _counter(name: str, description: str, labels: tuple[str, ...] = ()) -> Counter:
    existing = _find_existing(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    return Counter(name, description, labels)


def _gauge(name: str, description: str, labels: tuple[str, ...] = ()) -> Gauge:
    existing = _find_existing(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    return Gauge(name, description, labels)


def _histogram(
    name: str,
    description: str,
    labels: tuple[str, ...] = (),
    buckets: tuple[float, ...] | None = None,
) -> Histogram:
    existing = _find_existing(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    if buckets is None:
        return Histogram(name, description, labels)
    return Histogram(name, description, labels, buckets=buckets)


def _find_existing(name: str):
    # prometheus_client raises ValueError on duplicate registration. We look it
    # up so reloads (e.g. pytest collecting the module twice under autoreload)
    # don't blow up.
    for collector, names in list(REGISTRY._collector_to_names.items()):  # type: ignore[attr-defined]
        if name in names:
            return collector
    return None


# ---------------------------------------------------------------------------
# HTTP metrics
# ---------------------------------------------------------------------------

HTTP_REQUEST_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)

http_requests_total = _counter(
    "http_requests_total",
    "Total HTTP requests processed, labelled by method/route/status.",
    ("method", "route", "status"),
)

http_request_duration_seconds = _histogram(
    "http_request_duration_seconds",
    "HTTP request handler duration in seconds.",
    ("method", "route"),
    buckets=HTTP_REQUEST_BUCKETS,
)


# ---------------------------------------------------------------------------
# Database pool metrics (sampled lazily by the /metrics endpoint)
# ---------------------------------------------------------------------------

db_pool_size = _gauge(
    "db_pool_size",
    "Configured SQLAlchemy connection pool size (max).",
)
db_pool_in_use = _gauge(
    "db_pool_in_use",
    "Currently checked-out SQLAlchemy connections.",
)


def sample_db_pool() -> None:
    """Best-effort snapshot of the SQLAlchemy connection pool gauges."""

    try:
        from app.db import engine

        pool = engine.sync_engine.pool  # async engine wraps a sync pool
    except Exception:  # pragma: no cover - import or attr issues
        return

    size_fn = getattr(pool, "size", None)
    checked_out_fn = getattr(pool, "checkedout", None)
    try:
        if callable(size_fn):
            db_pool_size.set(float(size_fn()))
        if callable(checked_out_fn):
            db_pool_in_use.set(float(checked_out_fn()))
    except Exception:  # pragma: no cover - some pools (NullPool) don't expose these
        return


# ---------------------------------------------------------------------------
# Celery metrics
# ---------------------------------------------------------------------------

CELERY_TASK_BUCKETS: tuple[float, ...] = (
    0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0,
)

celery_tasks_total = _counter(
    "celery_tasks_total",
    "Total Celery tasks observed, labelled by queue/task/state.",
    ("queue", "task", "state"),
)

celery_task_duration_seconds = _histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds.",
    ("queue", "task"),
    buckets=CELERY_TASK_BUCKETS,
)


# ---------------------------------------------------------------------------
# Domain metrics — submissions, receipts, auth, CSRF
# ---------------------------------------------------------------------------

SUBMISSION_DURATION_BUCKETS: tuple[float, ...] = (
    0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0,
)

submissions_total = _counter(
    "submissions_total",
    "Total submission attempts, labelled by portal/status.",
    ("portal", "status"),
)

submissions_in_flight = _gauge(
    "submissions_in_flight",
    "Submissions currently being processed, labelled by portal.",
    ("portal",),
)

submission_duration_seconds = _histogram(
    "submission_duration_seconds",
    "End-to-end submission duration in seconds.",
    ("portal",),
    buckets=SUBMISSION_DURATION_BUCKETS,
)

receipts_signed_total = _counter(
    "receipts_signed_total",
    "Total signed receipts emitted, labelled by signing key id.",
    ("key_id",),
)

auth_logins_total = _counter(
    "auth_logins_total",
    "Authentication login attempts, labelled by outcome.",
    ("result",),
)

csrf_failures_total = _counter(
    "csrf_failures_total",
    "CSRF token rejections (missing or mismatched).",
)


__all__ = [
    "DEFAULT_REGISTRY",
    "HTTP_REQUEST_BUCKETS",
    "http_requests_total",
    "http_request_duration_seconds",
    "db_pool_size",
    "db_pool_in_use",
    "sample_db_pool",
    "celery_tasks_total",
    "celery_task_duration_seconds",
    "submissions_total",
    "submissions_in_flight",
    "submission_duration_seconds",
    "receipts_signed_total",
    "auth_logins_total",
    "csrf_failures_total",
]
