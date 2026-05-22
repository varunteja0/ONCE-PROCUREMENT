from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.logging import get_logger
from app.utils.security import TokenDecodeError, decode_token

__all__ = ["TenantScopeMiddleware"]


_logger = get_logger(__name__)

_DEFAULT_SKIP_PREFIXES: tuple[str, ...] = (
    "/health",
    "/v1/auth/",
    "/verify/",
)


class TenantScopeMiddleware(BaseHTTPMiddleware):
    """Populate ``request.state.tenant_id`` / ``request.state.user_id`` from a Bearer JWT.

    The middleware is intentionally permissive: if the ``Authorization`` header is
    missing, malformed, or the JWT fails to decode, request state is simply left
    unset and downstream dependencies (e.g. ``get_current_user``) are responsible
    for raising the appropriate ``401``. Decode errors are never propagated from
    the middleware itself.

    Paths matching any of the configured skip prefixes bypass JWT decoding entirely
    so that unauthenticated endpoints (health checks, login, public receipt
    verification) incur no overhead.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_prefixes: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._skip_prefixes: tuple[str, ...] = (
            tuple(skip_prefixes) if skip_prefixes is not None else _DEFAULT_SKIP_PREFIXES
        )

    def _should_skip(self, path: str) -> bool:
        for prefix in self._skip_prefixes:
            if prefix.endswith("/"):
                if path == prefix.rstrip("/") or path.startswith(prefix):
                    return True
            else:
                if path == prefix or path.startswith(prefix + "/"):
                    return True
        return False

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.tenant_id = None
        request.state.user_id = None

        if not self._should_skip(request.url.path):
            auth_header = request.headers.get("authorization") or request.headers.get(
                "Authorization"
            )
            if auth_header:
                scheme, _, token = auth_header.partition(" ")
                if scheme.lower() == "bearer" and token:
                    try:
                        payload = decode_token(token, expected_type="access")
                    except TokenDecodeError:
                        # Intentionally swallow: endpoint deps will issue 401.
                        pass
                    else:
                        tenant_id = payload.get("tenant_id")
                        sub = payload.get("sub")
                        if tenant_id:
                            request.state.tenant_id = str(tenant_id)
                        if sub:
                            request.state.user_id = str(sub)

        return await call_next(request)
