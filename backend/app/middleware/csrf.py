from __future__ import annotations

import hmac
import secrets
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

CSRF_COOKIE_NAME = "once_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
DEFAULT_BYPASS_PREFIXES: tuple[str, ...] = (
    "/v1/auth/",
    "/v1/webhooks/",
    "/v1/public/",
    "/webhooks/",
    "/health",
    "/ready",
    "/verify/",
)
TOKEN_BYTES = 24  # 24 bytes -> 32 chars urlsafe base64


def _generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)[:32]


def _is_bypassed_path(path: str, bypass_prefixes: Iterable[str]) -> bool:
    return any(path.startswith(prefix) for prefix in bypass_prefixes)


def _has_bearer_auth(request: Request) -> bool:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return False
    return auth.strip().lower().startswith("bearer ")


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit-cookie CSRF protection for browser clients.

    - Issues an `once_csrf` cookie on safe requests when missing. The cookie is
      readable from JavaScript (httponly=False) so SPA code can echo it back in
      the `X-CSRF-Token` header.
    - Rejects state-changing requests whose header value does not match the
      cookie value (constant-time comparison).
    - Bypasses paths used by API clients / unauth flows and any request that
      authenticates via `Authorization: Bearer ...`.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        cookie_name: str = CSRF_COOKIE_NAME,
        header_name: str = CSRF_HEADER_NAME,
        bypass_prefixes: tuple[str, ...] = DEFAULT_BYPASS_PREFIXES,
    ) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name.lower()
        self.bypass_prefixes = bypass_prefixes
        self.is_production = (getattr(settings, "app_env", "development") or "development").lower() == "production"

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        method = request.method.upper()
        existing_cookie = request.cookies.get(self.cookie_name)

        bypass = (
            _is_bypassed_path(path, self.bypass_prefixes)
            or _has_bearer_auth(request)
            or method in SAFE_METHODS
        )

        if not bypass:
            header_token = request.headers.get(self.header_name)
            if not existing_cookie or not header_token:
                logger.warning(
                    "csrf.missing_token",
                    path=path,
                    method=method,
                    has_cookie=bool(existing_cookie),
                    has_header=bool(header_token),
                )
                return JSONResponse(
                    {"detail": "CSRF token missing"},
                    status_code=403,
                )
            if not hmac.compare_digest(existing_cookie, header_token):
                logger.warning("csrf.token_mismatch", path=path, method=method)
                return JSONResponse(
                    {"detail": "CSRF token invalid"},
                    status_code=403,
                )

        response = await call_next(request)

        if existing_cookie is None and method in SAFE_METHODS:
            token = _generate_token()
            response.set_cookie(
                key=self.cookie_name,
                value=token,
                max_age=60 * 60 * 8,
                httponly=False,
                secure=self.is_production,
                samesite="lax",
                path="/",
            )

        return response


__all__ = ["CSRFMiddleware", "CSRF_COOKIE_NAME", "CSRF_HEADER_NAME"]
