"""Idempotency-Key middleware.

Lets clients safely retry mutating requests (``POST`` / ``PATCH`` /
``DELETE``) without producing duplicate side effects. The contract follows
the IETF `Idempotency-Key` draft and Stripe's de-facto behavior:

* Client sends ``Idempotency-Key: <ulid-or-uuid>`` on a mutating request.
* Server, on first success, caches ``(tenant_id, key) → (status, body,
  body_hash, headers, ts)`` in Redis (or an in-process fallback) for
  :data:`DEFAULT_TTL_SECONDS` (24 h).
* Replay with the **same key + same body hash** → cached response served
  with header ``Idempotency-Replayed: true``.
* Replay with the **same key + different body** → 422
  ``idempotency_key_conflict`` Problem response.
* If the key format is invalid → 400 ``invalid_idempotency_key``.
* If the key is missing on a mutating method and the route is registered
  as *required* → 400 ``idempotency_key_required``. By default keys are
  *optional*.

Toggleable via ``ENABLE_IDEMPOTENCY_MIDDLEWARE=true`` (defaults to
``false``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.utils.errors import (
    PROBLEM_CONTENT_TYPE,
    ProblemResponse,
    build_problem,
)
from app.utils.logging import get_logger

__all__ = [
    "IdempotencyMiddleware",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "RedisIdempotencyStore",
    "DEFAULT_TTL_SECONDS",
    "MUTATING_METHODS",
    "build_default_store",
]

_logger = get_logger(__name__)

DEFAULT_TTL_SECONDS: int = 24 * 60 * 60
MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PATCH", "PUT", "DELETE"})

# UUID4 (hyphenated or hex) OR ULID (26-char Crockford base32).
_KEY_RE = re.compile(
    r"^(?:[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z0-9]{26}|[0-9a-fA-F]{32}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


def _is_valid_key(value: str) -> bool:
    return bool(value) and bool(_KEY_RE.match(value))


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


# ---------------------------------------------------------------------------
# Store abstraction
# ---------------------------------------------------------------------------


class IdempotencyStore(Protocol):  # pragma: no cover - typing only
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict, ttl_seconds: int) -> None: ...
    def clear(self) -> None: ...


class InMemoryIdempotencyStore:
    """Thread-safe in-process store; default fallback when Redis is absent."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return dict(payload)

    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        expires_at = time.time() + max(int(ttl_seconds), 1)
        with self._lock:
            self._data[key] = (expires_at, dict(value))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisIdempotencyStore:
    """Redis-backed store; mirrors :class:`InMemoryIdempotencyStore`."""

    def __init__(self, client: object, *, namespace: str = "once:idem:") -> None:
        self._r = client
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}{key}"

    def get(self, key: str) -> dict | None:
        raw = self._r.get(self._k(key))  # type: ignore[attr-defined]
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):  # pragma: no cover - defensive
            return None

    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        payload = json.dumps(value, separators=(",", ":"))
        self._r.set(self._k(key), payload, ex=max(int(ttl_seconds), 1))  # type: ignore[attr-defined]

    def clear(self) -> None:  # pragma: no cover - tests use in-memory
        pass


def build_default_store() -> IdempotencyStore:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return InMemoryIdempotencyStore()
    try:
        import redis  # type: ignore[import-not-found]

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=0.25)
        client.ping()
        return RedisIdempotencyStore(client)
    except Exception as exc:  # pragma: no cover - exercised manually
        _logger.warning(
            "idempotency_redis_unavailable",
            error=str(exc),
            fallback="in_memory",
        )
        return InMemoryIdempotencyStore()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Caches successful mutating responses by ``Idempotency-Key``.

    Args:
        app: ASGI application.
        store: Storage backend; defaults to :func:`build_default_store`.
        required_path_prefixes: Optional iterable of URL path prefixes for
            which the key is **mandatory** (missing key → 400). All other
            paths treat the header as advisory.
        excluded_path_prefixes: Iterable of path prefixes that bypass the
            middleware entirely (auth, webhooks, etc.).
        ttl_seconds: Cache lifetime per key.
    """

    HEADER = "Idempotency-Key"
    REPLAY_HEADER = "Idempotency-Replayed"

    def __init__(
        self,
        app: ASGIApp,
        *,
        store: IdempotencyStore | None = None,
        required_path_prefixes: Iterable[str] = (),
        excluded_path_prefixes: Iterable[str] = (
            "/v1/auth/",
            "/v1/webhooks/",
            "/health",
            "/metrics",
            "/verify/",
        ),
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        super().__init__(app)
        self.store = store or build_default_store()
        self.required_path_prefixes = tuple(required_path_prefixes)
        self.excluded_path_prefixes = tuple(excluded_path_prefixes)
        self.ttl_seconds = int(ttl_seconds)

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.excluded_path_prefixes)

    def _is_required(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.required_path_prefixes)

    @staticmethod
    def _tenant_id(request: Request) -> str:
        return str(getattr(request.state, "tenant_id", "") or "anon")

    @staticmethod
    def _scoped_key(tenant_id: str, key: str) -> str:
        return f"{tenant_id}:{key}"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method not in MUTATING_METHODS or self._is_excluded(request.url.path):
            return await call_next(request)

        header_value = request.headers.get(self.HEADER, "").strip()
        if not header_value:
            if self._is_required(request.url.path):
                return ProblemResponse(
                    build_problem(
                        status=400,
                        title="Idempotency key required",
                        type_slug="idempotency-key-required",
                        detail="This endpoint requires an Idempotency-Key header.",
                        instance=request.url.path,
                    )
                )
            return await call_next(request)

        if not _is_valid_key(header_value):
            return ProblemResponse(
                build_problem(
                    status=400,
                    title="Invalid idempotency key",
                    type_slug="invalid-idempotency-key",
                    detail="Idempotency-Key must be a UUID or ULID.",
                    instance=request.url.path,
                )
            )

        body = await request.body()
        body_hash = _hash_body(body)
        # Re-inject body so downstream handlers can re-read it.
        request._body = body  # type: ignore[attr-defined]

        scoped = self._scoped_key(self._tenant_id(request), header_value)
        cached = self.store.get(scoped)
        if cached is not None:
            if cached.get("body_hash") != body_hash:
                return ProblemResponse(
                    build_problem(
                        status=422,
                        title="Idempotency key conflict",
                        type_slug="idempotency-key-conflict",
                        detail=(
                            "Idempotency-Key was reused with a different request body."
                        ),
                        instance=request.url.path,
                    )
                )
            headers = dict(cached.get("headers") or {})
            headers[self.REPLAY_HEADER] = "true"
            return Response(
                content=cached.get("body", ""),
                status_code=int(cached.get("status", 200)),
                headers=headers,
                media_type=cached.get("media_type") or "application/json",
            )

        response = await call_next(request)
        if 200 <= response.status_code < 300:
            response_body = b""
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                response_body += chunk
            # Strip hop-by-hop & sensitive headers we shouldn't replay.
            safe_headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower()
                not in {
                    "content-length",
                    "transfer-encoding",
                    "connection",
                    "set-cookie",
                }
            }
            self.store.set(
                scoped,
                {
                    "status": response.status_code,
                    "body": response_body.decode("utf-8", errors="replace"),
                    "body_hash": body_hash,
                    "headers": safe_headers,
                    "media_type": response.media_type or "application/json",
                    "ts": time.time(),
                },
                self.ttl_seconds,
            )
            # Rebuild response since we consumed the iterator.
            new_headers = dict(response.headers)
            new_headers.pop("content-length", None)
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=new_headers,
                media_type=response.media_type,
            )
        # Don't cache problem responses — but make sure we forward them
        # untouched (BaseHTTPMiddleware already streams body).
        if response.media_type == PROBLEM_CONTENT_TYPE:
            return response
        return response
