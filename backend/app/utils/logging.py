from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import settings

_CONFIGURED: bool = False


def _resolve_level() -> int:
    raw = (os.environ.get("LOG_LEVEL") or "").strip().upper()
    if raw and raw in logging._nameToLevel:
        return logging._nameToLevel[raw]
    return logging.DEBUG if settings.is_development else logging.INFO


def _service_name() -> str:
    return (os.environ.get("ONCE_SERVICE") or "api").strip() or "api"


def _add_service(_, __, event_dict):  # type: ignore[no-untyped-def]
    event_dict.setdefault("service", _service_name())
    return event_dict


def _build_processors(is_dev: bool) -> list[Processor]:
    from app.middleware.secrets_redaction import structlog_redactor

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_service,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog_redactor,
    ]
    if is_dev:
        # ConsoleRenderer formats exceptions itself; adding format_exc_info upstream
        # triggers a UserWarning per log line. Keep it for JSON/prod only.
        shared.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        shared.append(structlog.processors.format_exc_info)
        shared.append(structlog.processors.EventRenamer("message"))
        shared.append(structlog.processors.JSONRenderer())
    return shared


def configure_logging(force: bool = False) -> None:
    """Configure structlog + stdlib logging exactly once.

    - Dev (``APP_ENV=development``): coloured console renderer for easy reading.
    - Anything else: JSON renderer suitable for Loki / Cloud log shippers.
    - Honors ``LOG_LEVEL`` env override.
    - Captures stdlib ``warnings`` so deprecations land in the same pipeline.
    """

    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    is_dev = settings.is_development
    level = _resolve_level()

    processors = _build_processors(is_dev)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=(
            structlog.dev.ConsoleRenderer(colors=True)
            if is_dev
            else structlog.processors.JSONRenderer()
        ),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            _add_service,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).handlers = []
        logging.getLogger(noisy).propagate = True

    # Route Python warnings through the same handler so they appear as
    # structured log lines.
    logging.captureWarnings(True)

    _CONFIGURED = True


def bind_request_context(
    *,
    request_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Bind per-request context onto the structlog contextvars."""

    bindings: dict[str, Any] = {}
    if request_id is not None:
        bindings["request_id"] = request_id
    if tenant_id is not None:
        bindings["tenant_id"] = tenant_id
    if user_id is not None:
        bindings["user_id"] = user_id
    if bindings:
        structlog.contextvars.bind_contextvars(**bindings)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, configuring the pipeline on first use."""

    if not _CONFIGURED:
        configure_logging()
    logger = structlog.get_logger(name) if name else structlog.get_logger()
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_request_context",
    "clear_request_context",
]
