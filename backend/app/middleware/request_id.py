"""Request-ID middleware.

Reads ``X-Request-ID`` from the incoming request (generating a fresh UUID4 if
absent), stores it in a ``contextvars.ContextVar`` so structlog auto-binds it,
exposes it on ``request.state.request_id``, and echoes it back as a response
header.

The contextvar is intentionally module-level so workers (Celery) and any
background task spawned from the request context inherit the id.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"

# Public contextvar — imported by logging.py for structlog binding.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# UUIDs (with or without hyphens) and ULID-like 26-char Crockford-base32 ids.
_VALID_RE = re.compile(r"^[A-Za-z0-9_\-]{8,128}$")


def _generate_request_id() -> str:
    return uuid.uuid4().hex


def _is_valid(value: str) -> bool:
    return bool(_VALID_RE.match(value))


def set_request_id(value: str | None) -> str:
    """Set the current request_id contextvar and bind it for structlog."""

    rid = value if (value and _is_valid(value)) else _generate_request_id()
    request_id_var.set(rid)
    structlog.contextvars.bind_contextvars(request_id=rid)
    return rid


def clear_request_id() -> None:
    request_id_var.set(None)
    structlog.contextvars.unbind_contextvars("request_id")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate / propagate a request id for every HTTP request."""

    def __init__(self, app: ASGIApp, *, header_name: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(self.header_name)
        rid = set_request_id(incoming)
        request.state.request_id = rid
        try:
            response = await call_next(request)
        finally:
            # Don't leak across the connection pool reuse boundary.
            clear_request_id()
        response.headers[self.header_name] = rid
        return response


__all__ = [
    "RequestIDMiddleware",
    "REQUEST_ID_HEADER",
    "request_id_var",
    "set_request_id",
    "clear_request_id",
]
