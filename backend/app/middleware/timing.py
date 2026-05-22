"""Timing middleware.

Measures total handler duration, emits a ``Server-Timing`` response header,
records the request into the Prometheus histogram, and increments the request
counter. Route labels are taken from the FastAPI route template to keep
cardinality bounded.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.observability_extras import (
    http_request_duration_seconds,
    http_requests_total,
)

DEFAULT_METRICS_SKIP_PATHS: tuple[str, ...] = ("/metrics",)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    tmpl = getattr(route, "path", None)
    if tmpl:
        return tmpl
    # No route matched (404). Bucket as ``unmatched`` to avoid raw-path
    # cardinality explosion from scanners.
    return "unmatched"


class TimingMiddleware(BaseHTTPMiddleware):
    """Server-Timing header + Prometheus histogram for every request."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_paths: Iterable[str] = DEFAULT_METRICS_SKIP_PATHS,
    ) -> None:
        super().__init__(app)
        self._skip_paths = tuple(skip_paths)

    def _should_skip(self, path: str) -> bool:
        return any(path == s or path.startswith(s + "/") for s in self._skip_paths)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self._should_skip(request.url.path):
            return await call_next(request)

        start = time.perf_counter()
        method = request.method
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration = time.perf_counter() - start
            route = _route_label(request)
            http_request_duration_seconds.labels(method=method, route=route).observe(duration)
            http_requests_total.labels(method=method, route=route, status="500").inc()
            raise

        duration = time.perf_counter() - start
        route = _route_label(request)
        http_request_duration_seconds.labels(method=method, route=route).observe(duration)
        http_requests_total.labels(
            method=method, route=route, status=str(status_code)
        ).inc()

        # Server-Timing header (ms, three decimal places).
        response.headers["Server-Timing"] = f"total;dur={duration * 1000.0:.3f}"
        return response


__all__ = ["TimingMiddleware"]
