"""HTTP security-headers middleware.

Adds a defense-in-depth set of response headers on every response coming out
of the FastAPI application.

Header strategy (fail-closed defaults; configurable via env):

* ``Strict-Transport-Security`` — emitted only when ``SECURITY_HSTS_ENABLED``
  is truthy AND the request was not against ``localhost`` / ``127.0.0.1`` (to
  keep local dev workflows sane).  Defaults to **on** when ``APP_ENV`` /
  ``ENV`` is ``production``.
* ``X-Content-Type-Options: nosniff`` — always.
* ``X-Frame-Options: DENY`` — always (the API never renders pages that need
  to be embedded; the verifier badge endpoint lives in a separate service and
  manages its own headers).
* ``Referrer-Policy: strict-origin-when-cross-origin`` — always.
* ``Permissions-Policy`` — explicitly denies camera / mic / geolocation /
  payment / USB / accelerometer (we use none of those).
* ``Cross-Origin-Opener-Policy: same-origin`` — process isolation for any
  HTML we render (docs UI etc.).
* ``Cross-Origin-Resource-Policy: same-site`` — block cross-origin embeds of
  our JSON resources.
* ``Content-Security-Policy`` — only attached when the response content-type
  is ``text/html`` (the API is JSON-first; CSP on JSON responses is wasted
  bytes and confuses some clients).  Optional ``SECURITY_CSP_REPORT_URI``
  appends ``report-uri`` / ``report-to`` directives.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings

__all__ = ["SecurityHeadersMiddleware", "build_security_headers"]


_LOCAL_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1", "testserver"})


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _hsts_default_enabled() -> bool:
    env = (getattr(settings, "env", None) or getattr(settings, "app_env", "")).lower()
    return env == "production"


def _hsts_value() -> str:
    # 2 years, includeSubDomains, preload — matches the canonical preload-list
    # requirements.
    return "max-age=63072000; includeSubDomains; preload"


def _csp_value(report_uri: str | None) -> str:
    base = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'"
    )
    if report_uri:
        base += f"; report-uri {report_uri}"
    return base


def build_security_headers(
    *,
    is_local: bool,
    hsts_enabled: bool,
    is_html: bool,
    csp_report_uri: str | None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), payment=(), "
            "usb=(), accelerometer=(), gyroscope=(), magnetometer=()"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-site",
    }
    if hsts_enabled and not is_local:
        headers["Strict-Transport-Security"] = _hsts_value()
    if is_html:
        headers["Content-Security-Policy"] = _csp_value(csp_report_uri)
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardened security headers to every outbound response."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        hsts_enabled: bool | None = None,
        csp_report_uri: str | None = None,
    ) -> None:
        super().__init__(app)
        self._hsts_enabled = (
            hsts_enabled
            if hsts_enabled is not None
            else _env_bool("SECURITY_HSTS_ENABLED", _hsts_default_enabled())
        )
        self._csp_report_uri = (
            csp_report_uri
            if csp_report_uri is not None
            else (os.environ.get("SECURITY_CSP_REPORT_URI") or None)
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], object],
    ) -> Response:
        response: Response = await call_next(request)  # type: ignore[assignment]

        host_header = (request.headers.get("host") or "").split(":", 1)[0].strip().lower()
        is_local = host_header in _LOCAL_HOSTS

        content_type = (response.headers.get("content-type") or "").lower()
        is_html = content_type.startswith("text/html")

        for key, value in build_security_headers(
            is_local=is_local,
            hsts_enabled=self._hsts_enabled,
            is_html=is_html,
            csp_report_uri=self._csp_report_uri,
        ).items():
            # Don't clobber a header explicitly set by a downstream handler.
            response.headers.setdefault(key, value)

        return response
