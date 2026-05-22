"""Standardized error envelope + exception → response mapping.

Implements RFC 9457 ``application/problem+json`` for the Once API. The
mapping is wired by calling :func:`install_error_handlers` on a FastAPI app
(tests do so explicitly; production opt-in is documented in
``docs/API.md``).

Backward compatibility:

* the Problem envelope **always** carries a top-level ``detail`` field
  (alias of ``title``) so existing clients reading ``response.json()["detail"]``
  continue to work;
* legacy structured-detail payloads
  (``HTTPException(detail={"code": ..., "message": ...})``) are surfaced
  verbatim in ``detail`` as well — only ``type`` / ``title`` / ``trace_id``
  are added on top.

The module also defines a small hierarchy of :class:`DomainError` subclasses
that route / service code may raise. Each carries its own ``type_slug`` so
the resulting Problem ``type`` URI is stable.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.schemas.common import PROBLEM_BASE_URL, Problem, ValidationErrorItem
from app.utils.logging import get_logger

__all__ = [
    "DomainError",
    "NotFoundError",
    "ConflictError",
    "PreconditionFailedError",
    "IdempotencyKeyConflictError",
    "RateLimitedError",
    "ProblemResponse",
    "build_problem",
    "install_error_handlers",
    "PROBLEM_CONTENT_TYPE",
]

_logger = get_logger(__name__)


PROBLEM_CONTENT_TYPE: str = "application/problem+json"


# ---------------------------------------------------------------------------
# Domain exception hierarchy
# ---------------------------------------------------------------------------


class DomainError(Exception):
    """Base class for service-level errors mapped to a Problem response.

    Subclasses override ``status_code``, ``title``, and ``type_slug`` (the
    final URI path segment under :data:`PROBLEM_BASE_URL`).
    """

    status_code: int = 500
    title: str = "Internal server error"
    type_slug: str = "internal-server-error"

    def __init__(
        self,
        detail: Any = None,
        *,
        errors: list[ValidationErrorItem] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail if detail is not None else self.title)
        self.detail = detail if detail is not None else self.title
        self.errors = errors
        self.headers = dict(headers) if headers else None

    @property
    def type_uri(self) -> str:
        return f"{PROBLEM_BASE_URL}/{self.type_slug}"


class NotFoundError(DomainError):
    status_code = 404
    title = "Resource not found"
    type_slug = "not-found"


class ConflictError(DomainError):
    status_code = 409
    title = "Conflict"
    type_slug = "conflict"


class PreconditionFailedError(DomainError):
    status_code = 412
    title = "Precondition failed"
    type_slug = "precondition-failed"


class IdempotencyKeyConflictError(DomainError):
    status_code = 422
    title = "Idempotency key conflict"
    type_slug = "idempotency-key-conflict"


class RateLimitedError(DomainError):
    status_code = 429
    title = "Rate limit exceeded"
    type_slug = "rate-limited"


# ---------------------------------------------------------------------------
# Problem builder
# ---------------------------------------------------------------------------


_STATUS_TYPE_SLUGS: dict[int, str] = {
    400: "bad-request",
    401: "unauthorized",
    403: "forbidden",
    404: "not-found",
    405: "method-not-allowed",
    409: "conflict",
    410: "gone",
    412: "precondition-failed",
    415: "unsupported-media-type",
    422: "unprocessable-entity",
    429: "rate-limited",
    500: "internal-server-error",
    502: "bad-gateway",
    503: "service-unavailable",
    504: "gateway-timeout",
}


_STATUS_TITLES: dict[int, str] = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    410: "Gone",
    412: "Precondition failed",
    415: "Unsupported media type",
    422: "Unprocessable entity",
    429: "Too many requests",
    500: "Internal server error",
    502: "Bad gateway",
    503: "Service unavailable",
    504: "Gateway timeout",
}


def _resolve_trace_id(request: Request | None) -> str | None:
    """Pull the request id out of request state / contextvars, if any."""

    if request is not None:
        tid = getattr(request.state, "request_id", None)
        if tid:
            return str(tid)
    try:
        from app.middleware.request_id import request_id_var

        rid = request_id_var.get()
        if rid:
            return str(rid)
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def build_problem(
    *,
    status: int,
    title: str | None = None,
    detail: Any = None,
    type_slug: str | None = None,
    instance: str | None = None,
    trace_id: str | None = None,
    errors: list[ValidationErrorItem] | None = None,
) -> Problem:
    """Construct a :class:`Problem` with sensible defaults filled in."""

    slug = type_slug or _STATUS_TYPE_SLUGS.get(status, "about:blank")
    resolved_title = title or _STATUS_TITLES.get(status, "Error")
    # Backward-compat: surface ``detail`` even when caller passed only a title.
    resolved_detail: Any = detail if detail is not None else resolved_title
    return Problem(
        type=f"{PROBLEM_BASE_URL}/{slug}",
        title=resolved_title,
        status=status,
        detail=resolved_detail,
        instance=instance,
        trace_id=trace_id,
        errors=errors,
    )


class ProblemResponse(JSONResponse):
    """JSONResponse pre-configured for ``application/problem+json``."""

    media_type = PROBLEM_CONTENT_TYPE

    def __init__(
        self,
        problem: Problem,
        *,
        headers: MutableMapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=problem.status,
            content=problem.model_dump(mode="json", exclude_none=True),
            headers=dict(headers) if headers else None,
        )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _domain_error_handler(request: Request, exc: DomainError) -> ProblemResponse:
    trace_id = _resolve_trace_id(request)
    problem = build_problem(
        status=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        type_slug=exc.type_slug,
        instance=request.url.path,
        trace_id=trace_id,
        errors=exc.errors,
    )
    if exc.status_code >= 500:
        _logger.error(
            "domain_error",
            type=problem.type,
            status=exc.status_code,
            path=request.url.path,
            detail=str(exc.detail),
        )
    return ProblemResponse(problem, headers=exc.headers)


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> ProblemResponse:
    trace_id = _resolve_trace_id(request)
    problem = build_problem(
        status=exc.status_code,
        detail=exc.detail,
        instance=request.url.path,
        trace_id=trace_id,
    )
    if exc.status_code >= 500:
        _logger.error(
            "http_exception",
            status=exc.status_code,
            path=request.url.path,
            detail=str(exc.detail),
        )
    return ProblemResponse(problem, headers=getattr(exc, "headers", None) or None)


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ProblemResponse:
    raw_errors = exc.errors()
    items: list[ValidationErrorItem] = []
    for err in raw_errors:
        items.append(
            ValidationErrorItem(
                loc=list(err.get("loc") or []),
                msg=str(err.get("msg") or ""),
                code=str(err.get("type")) if err.get("type") is not None else None,
            )
        )
    trace_id = _resolve_trace_id(request)
    problem = build_problem(
        status=422,
        title="Unprocessable entity",
        # Preserve legacy shape: detail is the raw pydantic list.
        detail=raw_errors,
        instance=request.url.path,
        trace_id=trace_id,
        errors=items,
    )
    _logger.info("validation_error", path=request.url.path, error_count=len(items))
    return ProblemResponse(problem)


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> ProblemResponse:
    trace_id = _resolve_trace_id(request)
    problem = build_problem(
        status=500,
        title="Internal server error",
        detail="internal_server_error",
        type_slug="internal-server-error",
        instance=request.url.path,
        trace_id=trace_id,
    )
    _logger.exception(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        error_type=exc.__class__.__name__,
    )
    return ProblemResponse(problem)


def install_error_handlers(app: FastAPI) -> None:
    """Register the RFC-9457 Problem envelope handlers on ``app``.

    Idempotent — calling twice is safe (later registrations overwrite).
    """

    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
