"""Conditional-request middleware.

Implements the response side of RFC 7232 / 9110 for ``GET`` (and ``HEAD``)
responses:

* computes a weak ``ETag`` (SHA-256 of the body) for every successful 2xx
  response that doesn't already carry one;
* honors ``If-None-Match``: if any presented tag matches the computed
  ETag, the response is replaced with a bare ``304 Not Modified``.

The state-changing side (``If-Match`` for ``PUT`` / ``PATCH`` / ``DELETE``)
is route-driven via :func:`app.utils.etag.check_if_match` — concurrency
control needs the *resource's* ETag (not the response body's), so it lives
inside route handlers where that information is available.

Toggleable via ``ENABLE_CONDITIONAL_REQUEST_MIDDLEWARE=true`` (default
``true``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.etag import compute_weak_etag, if_none_match_hits

__all__ = ["ConditionalRequestMiddleware"]


class ConditionalRequestMiddleware(BaseHTTPMiddleware):
    """Add ETag + handle If-None-Match for cacheable GET / HEAD responses."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        excluded_path_prefixes: Iterable[str] = (
            "/metrics",
            "/health",
        ),
    ) -> None:
        super().__init__(app)
        self.excluded_path_prefixes = tuple(excluded_path_prefixes)

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.excluded_path_prefixes)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method not in {"GET", "HEAD"} or self._is_excluded(
            request.url.path
        ):
            return await call_next(request)

        response = await call_next(request)
        if not (200 <= response.status_code < 300):
            return response

        # If a route already set ETag, respect it; otherwise compute one.
        existing_etag = response.headers.get("ETag")
        if existing_etag:
            etag = existing_etag
            body = b""
            need_rebuild = False
        else:
            body = b""
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body += chunk
            etag = compute_weak_etag(body)
            need_rebuild = True

        if if_none_match_hits(request, etag):
            not_modified_headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower() in {"cache-control", "vary", "x-api-version", "x-request-id"}
            }
            not_modified_headers["ETag"] = etag
            return Response(status_code=304, headers=not_modified_headers)

        if not need_rebuild:
            return response

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["ETag"] = etag
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
