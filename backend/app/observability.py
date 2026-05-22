"""Observability: Sentry initialization + structured exception handlers.

Packaged as a single module (rather than a package) because the deployment
sandbox cannot create new directories. The public surface is:

    from app.observability import init_sentry, register_exception_handlers

`init_sentry` is a safe no-op when the DSN is empty or `sentry-sdk` is not
installed. `register_exception_handlers` wires structured JSON error responses
and forwards 5xx / unhandled exceptions to Sentry when available.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.utils.logging import get_logger

_logger = get_logger(__name__)

_SENTRY_INITIALIZED: bool = False


# ---------------------------------------------------------------------------
# Sentry init
# ---------------------------------------------------------------------------


def init_sentry(
    dsn: str,
    environment: str,
    release: str,
    traces_sample_rate: float = 0.1,
) -> bool:
    """Initialize Sentry with FastAPI + SQLAlchemy + Celery integrations.

    Returns True if Sentry was initialized, False otherwise (empty DSN,
    missing `sentry-sdk` package, or already initialized).
    """

    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
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

    try:
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        integrations.append(SqlalchemyIntegration())
    except ImportError:  # pragma: no cover - optional
        _logger.debug("sentry_sqlalchemy_integration_unavailable")

    try:
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration(monitor_beat_tasks=True))
    except ImportError:  # pragma: no cover - optional
        _logger.debug("sentry_celery_integration_unavailable")

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=float(traces_sample_rate),
        integrations=integrations,
        send_default_pii=False,
        attach_stacktrace=True,
    )

    _SENTRY_INITIALIZED = True
    _logger.info(
        "sentry_initialized",
        environment=environment,
        release=release,
        traces_sample_rate=float(traces_sample_rate),
    )
    return True


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def _capture(exc: BaseException) -> None:
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - optional dep
        return
    try:
        sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - never let reporting raise
        _logger.exception("sentry_capture_failed")


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if exc.status_code >= 500:
        _logger.error(
            "http_exception",
            status_code=exc.status_code,
            path=request.url.path,
            detail=str(exc.detail),
        )
        _capture(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or None,
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    _logger.info(
        "validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    _logger.exception(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        error_type=exc.__class__.__name__,
    )
    _capture(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal_server_error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the canonical structured exception handlers on `app`."""

    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = ["init_sentry", "register_exception_handlers"]
