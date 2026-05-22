"""Structured JSON access log middleware.

Emits exactly one structlog event per request with the canonical fields the
Grafana / Loki dashboards expect. Health-probe noise (``/v1/health/live``) and
the Prometheus scrape endpoint (``/metrics``) are skipped.

The log call is funnelled through structlog so contextvar bindings (request_id,
tenant_id, user_id, service) are merged automatically — no double-logging via
stdlib loggers.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.logging import get_logger

_logger = get_logger("access")

DEFAULT_SKIP_PATHS: tuple[str, ...] = ("/v1/health/live", "/metrics")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    if request.client:
        return request.client.host
    return ""


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    if path_template:
        return path_template
    return request.url.path


class AccessLogMiddleware(BaseHTTPMiddleware):
    """One JSON access log line per request."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_paths: Iterable[str] = DEFAULT_SKIP_PATHS,
    ) -> None:
        super().__init__(app)
        self._skip_paths = tuple(skip_paths)

    def _should_skip(self, path: str) -> bool:
        return any(path == skip or path.startswith(skip + "/") for skip in self._skip_paths)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if self._should_skip(path):
            return await call_next(request)

        start = time.perf_counter()
        method = request.method
        bytes_in_hdr = request.headers.get("content-length")
        try:
            bytes_in = int(bytes_in_hdr) if bytes_in_hdr else 0
        except ValueError:
            bytes_in = 0
        client_ip = _client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        status_code = 500
        bytes_out = 0
        try:
            response = await call_next(request)
            status_code = response.status_code
            out_hdr = response.headers.get("content-length")
            try:
                bytes_out = int(out_hdr) if out_hdr else 0
            except ValueError:
                bytes_out = 0
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            tenant_id = getattr(request.state, "tenant_id", None)
            user_id = getattr(request.state, "user_id", None)
            request_id = getattr(request.state, "request_id", None)

            # Pull route template after dispatch so FastAPI has resolved the
            # match. Falls back to raw path.
            route_template = _route_template(request)

            event = {
                "method": method,
                "path": path,
                "route_template": route_template,
                "status": status_code,
                "duration_ms": round(duration_ms, 3),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "bytes_in": bytes_in,
                "bytes_out": bytes_out,
            }
            if tenant_id:
                event["tenant_id"] = tenant_id
            if user_id:
                event["user_id"] = user_id
            if request_id:
                event["request_id"] = request_id

            level = "info"
            if status_code >= 500:
                level = "error"
            elif status_code >= 400:
                level = "warning"

            getattr(_logger, level)("http_access", **event)


__all__ = ["AccessLogMiddleware", "DEFAULT_SKIP_PATHS"]
