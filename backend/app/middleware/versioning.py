"""API version negotiation middleware.

The canonical version lives in the URL prefix (``/v1/...``). For future
breaking changes we also support content-negotiation via the ``Accept``
header:

    Accept: application/vnd.once.v2+json

When (and only when) a versioned media type is presented and the requested
version is registered, the middleware sets ``request.state.api_version`` so
downstream routing can branch. Today the only registered version is
``v1`` — unknown versions silently fall back to v1 with a warning log; we
do NOT 406 because clients in the wild send all manner of Accept headers.

Every response carries ``X-API-Version: v1`` (or whatever was resolved) so
clients can detect server-side rollouts without parsing version strings.

Toggleable via ``ENABLE_VERSIONING_MIDDLEWARE=true`` (default ``true``).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.logging import get_logger

__all__ = [
    "ApiVersioningMiddleware",
    "DEFAULT_API_VERSION",
    "SUPPORTED_API_VERSIONS",
    "parse_accept_version",
]


DEFAULT_API_VERSION: str = "v1"
SUPPORTED_API_VERSIONS: tuple[str, ...] = ("v1",)

_ACCEPT_RE = re.compile(r"application/vnd\.once\.(v\d+)(?:\+json)?", re.IGNORECASE)

_logger = get_logger(__name__)


def parse_accept_version(
    accept_header: str | None,
    *,
    supported: Iterable[str] = SUPPORTED_API_VERSIONS,
    default: str = DEFAULT_API_VERSION,
) -> str:
    """Extract a vendor-tagged API version from an ``Accept`` header.

    Returns ``default`` if the header is absent, unparseable, or names an
    unsupported version. The caller cannot tell the difference between
    "no header" and "unknown version" — this is intentional; the response
    ``X-API-Version`` header is the source of truth for what was served.
    """

    if not accept_header:
        return default
    supported_set = {v.lower() for v in supported}
    # Accept may carry multiple media types; first match wins.
    for chunk in accept_header.split(","):
        m = _ACCEPT_RE.search(chunk)
        if not m:
            continue
        candidate = m.group(1).lower()
        if candidate in supported_set:
            return candidate
        _logger.info(
            "api_version_unknown_requested",
            requested=candidate,
            fallback=default,
        )
        return default
    return default


class ApiVersioningMiddleware(BaseHTTPMiddleware):
    """Resolve API version from ``Accept`` and stamp ``X-API-Version``."""

    HEADER = "X-API-Version"

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_version: str = DEFAULT_API_VERSION,
        supported_versions: Iterable[str] = SUPPORTED_API_VERSIONS,
    ) -> None:
        super().__init__(app)
        self.default_version = default_version
        self.supported_versions = tuple(supported_versions)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        version = parse_accept_version(
            request.headers.get("Accept"),
            supported=self.supported_versions,
            default=self.default_version,
        )
        request.state.api_version = version
        response = await call_next(request)
        response.headers[self.HEADER] = version
        return response
