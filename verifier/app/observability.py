"""Sentry initialization for the Once Verifier microservice."""

from __future__ import annotations

from typing import Any

import structlog

_logger = structlog.get_logger(__name__)

_INITIALIZED: bool = False


def init_sentry(
    dsn: str,
    environment: str,
    release: str,
    traces_sample_rate: float = 0.1,
) -> bool:
    """Initialize Sentry with the FastAPI integration. No-op when dsn empty."""

    global _INITIALIZED
    if _INITIALIZED:
        return False
    if not dsn or not dsn.strip():
        _logger.info("sentry_disabled_no_dsn", environment=environment)
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError as exc:
        _logger.warning("sentry_sdk_unavailable", error=str(exc))
        return False

    integrations: list[Any] = [
        StarletteIntegration(transaction_style="endpoint"),
        FastApiIntegration(transaction_style="endpoint"),
    ]

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=float(traces_sample_rate),
        integrations=integrations,
        send_default_pii=False,
        attach_stacktrace=True,
    )

    _INITIALIZED = True
    _logger.info(
        "sentry_initialized",
        environment=environment,
        release=release,
        traces_sample_rate=float(traces_sample_rate),
    )
    return True


__all__ = ["init_sentry"]
