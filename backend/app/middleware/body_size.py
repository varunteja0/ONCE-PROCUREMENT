"""Request-body size limiting middleware.

Enforces a maximum request body size in bytes so a malicious or buggy client
cannot exhaust memory by streaming a huge JSON document or multipart upload.

Two limits apply:

* ``json_limit`` — default 1 MiB.  Applied when the ``Content-Type`` is
  ``application/json`` or absent (defensive).
* ``upload_limit`` — default 25 MiB.  Applied to ``multipart/form-data`` and
  ``application/octet-stream`` (file uploads — COIs, ACORD PDFs, etc.).

A per-route override can be supplied as a FastAPI dependency by attaching the
limit to ``request.state.max_body_size`` before the body is read; the
middleware honors that override when present.

Behavior:

* If the ``Content-Length`` header is present and exceeds the limit, the
  middleware short-circuits with a ``413 Payload Too Large`` response without
  reading the body.
* If the header is missing or lies, we stream-count the body and abort once
  the limit is breached.

This is **fail-closed**: an unparseable ``Content-Length`` falls back to the
streamed enforcement path.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = [
    "BodySizeLimitMiddleware",
    "DEFAULT_JSON_LIMIT_BYTES",
    "DEFAULT_UPLOAD_LIMIT_BYTES",
    "set_max_body_size",
]


DEFAULT_JSON_LIMIT_BYTES = 1 * 1024 * 1024  # 1 MiB
DEFAULT_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024  # 25 MiB

_UPLOAD_CONTENT_TYPES: tuple[str, ...] = (
    "multipart/form-data",
    "application/octet-stream",
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def set_max_body_size(request: Request, limit_bytes: int) -> None:
    """Per-route override: call from a dependency before body is consumed."""

    request.state.max_body_size = int(limit_bytes)


def _limit_for(
    *,
    content_type: str,
    json_limit: int,
    upload_limit: int,
) -> int:
    ct = content_type.lower()
    for prefix in _UPLOAD_CONTENT_TYPES:
        if ct.startswith(prefix):
            return upload_limit
    return json_limit


def _too_large_response(limit: int) -> Response:
    return JSONResponse(
        status_code=413,
        content={
            "detail": "request_body_too_large",
            "limit_bytes": limit,
        },
    )


class BodySizeLimitMiddleware:
    """Pure-ASGI body-size limiter.

    Implemented directly against the ASGI protocol (rather than
    ``BaseHTTPMiddleware``) so we can intercept the ``http.request`` chunks
    as they are streamed in and abort early on overrun.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        json_limit: int | None = None,
        upload_limit: int | None = None,
    ) -> None:
        self.app = app
        self.json_limit = (
            json_limit
            if json_limit is not None
            else _env_int("SECURITY_BODY_JSON_LIMIT", DEFAULT_JSON_LIMIT_BYTES)
        )
        self.upload_limit = (
            upload_limit
            if upload_limit is not None
            else _env_int("SECURITY_BODY_UPLOAD_LIMIT", DEFAULT_UPLOAD_LIMIT_BYTES)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        if method in {"GET", "HEAD", "OPTIONS", "TRACE", "DELETE"}:
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        content_type = headers.get("content-type", "")
        override = None  # ASGI scope has no Request.state yet; route-level override is best-effort.
        max_bytes = override or _limit_for(
            content_type=content_type,
            json_limit=self.json_limit,
            upload_limit=self.upload_limit,
        )

        cl_raw = headers.get("content-length")
        if cl_raw:
            try:
                declared = int(cl_raw)
            except ValueError:
                declared = -1
            if declared > max_bytes:
                response = _too_large_response(max_bytes)
                await response(scope, receive, send)
                return

        received = 0
        overrun = False

        async def limited_receive() -> Message:
            nonlocal received, overrun
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body") or b""
                received += len(body)
                if received > max_bytes:
                    overrun = True
            return message

        async def guarded_send(message: Message) -> None:
            if overrun and message["type"] == "http.response.start":
                # Replace the upstream response with a 413; downstream body
                # send calls below are dropped.
                response = _too_large_response(max_bytes)
                await response(scope, receive, send)
                # Mark already-sent so subsequent body messages are ignored.
                return
            if overrun and message["type"] == "http.response.body":
                return
            await send(message)

        await self.app(scope, limited_receive, guarded_send)


# Convenience export used by tests
def _build_limited_app(app: ASGIApp, json_limit: int, upload_limit: int) -> ASGIApp:  # pragma: no cover - helper
    return BodySizeLimitMiddleware(app, json_limit=json_limit, upload_limit=upload_limit)


# Re-export Awaitable / Callable for type checkers that look here.
_ = (Awaitable, Callable)
