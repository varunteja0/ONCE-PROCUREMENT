"""API-key auth + per-IP rate limiting for the public verifier.

The verifier itself stores nothing (see ``verifier/AGENTS.md``). Per-tenant
usage accounting lives in the main backend; this middleware simply forwards
the ``X-Verify-API-Key`` plaintext to the backend's internal
``/v1/internal/verifier-keys/charge`` endpoint and translates the response.

Behaviour for ``/verify/*`` paths:

* ``X-Verify-API-Key`` header present:
    * Backend returns 200 \u2192 attach ``request.state.api_key_id`` /
      ``request.state.api_key_tenant_id`` and pass through.
    * Backend returns 401 \u2192 respond 401 ``{"detail": {"code": "invalid_api_key"}}``.
    * Backend returns 402 \u2192 forward 402 body verbatim (quota exceeded).
    * Backend unreachable or other status \u2192 respond 503.
* No header \u2192 apply per-IP sliding-window rate limit using
  ``settings.unauth_rate_limit`` (e.g. ``"100/day;20/hour;5/minute"``).

All other paths (``/health``, ``/healthz``, ``/static``, root, badge, etc.)
are passed through untouched so health checks and static assets stay free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import structlog
from fastapi.responses import JSONResponse
from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Awaitable, Callable

    from fastapi import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)

API_KEY_HEADER = "X-Verify-API-Key"

_STORAGE = MemoryStorage()
_LIMITER = MovingWindowRateLimiter(_STORAGE)


def reset_rate_limit_storage() -> None:
    """Test hook: reset the in-process rate-limit storage."""

    global _STORAGE, _LIMITER  # noqa: PLW0603
    _STORAGE = MemoryStorage()
    _LIMITER = MovingWindowRateLimiter(_STORAGE)


def _is_verify_path(path: str) -> bool:
    # Covers /verify/{id}, /verify/{id}.html, /verify/{id}.json,
    # /verify/{id}/badge.svg \u2014 i.e. everything that consumes a backend call.
    return path.startswith("/verify/")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


async def _charge_backend(plaintext: str) -> tuple[int, dict[str, Any]]:
    from app.main import settings  # local import to avoid cycle

    if not settings.backend_internal_token:
        logger.warning("verifier_api_key_not_configured")
        return 503, {"detail": "Verifier API key auth not configured"}

    url = (
        f"{settings.backend_base_url.rstrip('/')}"
        "/v1/internal/verifier-keys/charge"
    )
    headers = {"X-Internal-Token": settings.backend_internal_token}
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_sec
        ) as client:
            resp = await client.post(
                url, json={"plaintext": plaintext}, headers=headers
            )
    except httpx.HTTPError as exc:
        logger.warning("verifier_charge_unreachable", error=str(exc))
        return 503, {"detail": "Verifier auth backend unreachable"}

    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {"detail": body}
    return resp.status_code, body


def _rate_limit_exceeded() -> JSONResponse:
    return JSONResponse(
        {
            "detail": (
                "Rate limit exceeded. Provide an X-Verify-API-Key to raise "
                "your limits."
            )
        },
        status_code=429,
        headers={"Retry-After": "60"},
    )


async def enforce_api_key_or_rate_limit(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """ASGI middleware: gate ``/verify/*`` on either an API key or per-IP rate."""

    if not _is_verify_path(request.url.path):
        return await call_next(request)

    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        status_code, body = await _charge_backend(api_key)
        if status_code == 200:
            request.state.api_key_id = body.get("api_key_id")
            request.state.api_key_tenant_id = body.get("tenant_id")
            return await call_next(request)
        if status_code == 401:
            return JSONResponse(
                {"detail": {"code": "invalid_api_key"}}, status_code=401
            )
        if status_code == 402:
            return JSONResponse(body, status_code=402)
        return JSONResponse(
            {"detail": "Verifier auth temporarily unavailable"},
            status_code=503,
        )

    # Unauthenticated \u2014 enforce per-IP rate limit.
    from app.main import settings  # local import to avoid cycle

    ip = _client_ip(request)
    for item in parse_many(settings.unauth_rate_limit):
        if not _LIMITER.hit(item, "verify", ip):
            return _rate_limit_exceeded()
    return await call_next(request)


__all__ = [
    "API_KEY_HEADER",
    "enforce_api_key_or_rate_limit",
    "reset_rate_limit_storage",
]
