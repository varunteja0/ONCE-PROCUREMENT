"""Sliding-window account lockout tracker.

Tracks failed login attempts per ``(email, ip)`` tuple so a single rogue IP
cannot lock out a legitimate user by spraying their email.  Uses Redis when
``REDIS_URL`` is reachable; falls back to a process-local in-memory store and
logs a warning otherwise.

Defaults (override via env):

* ``ACCOUNT_LOCKOUT_MAX_FAILS`` — 5
* ``ACCOUNT_LOCKOUT_WINDOW_SEC`` — 900 (15 min)
* ``ACCOUNT_LOCKOUT_DURATION_SEC`` — 1800 (30 min)

The store API is intentionally tiny — three methods — so the tests can swap
in a fakeredis-backed implementation by injecting a different ``store``.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil
from typing import Protocol

from app.utils.logging import get_logger

__all__ = [
    "LockoutStatus",
    "AccountLockoutTracker",
    "get_default_tracker",
    "reset_default_tracker",
]


_logger = get_logger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(slots=True, frozen=True)
class LockoutStatus:
    locked: bool
    failed_count: int
    retry_after_seconds: int


class _LockoutStore(Protocol):  # pragma: no cover - typing only
    def record_failure(self, key: str, window_sec: int) -> int: ...
    def lock(self, key: str, duration_sec: int) -> None: ...
    def status(self, key: str, window_sec: int) -> tuple[int, int]: ...
    def clear(self, key: str) -> None: ...


class _InMemoryStore:
    """Thread-safe in-process store. Used in tests and as a Redis fallback."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._locks: dict[str, float] = {}  # key -> unix_ts when lock expires
        self._lock = threading.Lock()

    def record_failure(self, key: str, window_sec: int) -> int:
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            bucket = [t for t in self._failures.get(key, []) if t >= cutoff]
            bucket.append(now)
            self._failures[key] = bucket
            return len(bucket)

    def lock(self, key: str, duration_sec: int) -> None:
        with self._lock:
            self._locks[key] = time.time() + duration_sec

    def status(self, key: str, window_sec: int) -> tuple[int, int]:
        now = time.time()
        cutoff = now - window_sec
        with self._lock:
            failures = [t for t in self._failures.get(key, []) if t >= cutoff]
            self._failures[key] = failures
            expires = self._locks.get(key)
            if expires is not None and expires <= now:
                del self._locks[key]
                expires = None
            retry_after = ceil(expires - now) if expires else 0
            return len(failures), max(retry_after, 0)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locks.pop(key, None)


class _RedisStore:
    """Redis-backed store using a sorted set of timestamps + a TTL key."""

    def __init__(self, client: object) -> None:
        self._r = client

    @staticmethod
    def _attempts_key(key: str) -> str:
        return f"once:lockout:attempts:{key}"

    @staticmethod
    def _lock_key(key: str) -> str:
        return f"once:lockout:lock:{key}"

    def record_failure(self, key: str, window_sec: int) -> int:
        now = time.time()
        attempts = self._attempts_key(key)
        pipe = self._r.pipeline()  # type: ignore[attr-defined]
        pipe.zadd(attempts, {str(now): now})
        pipe.zremrangebyscore(attempts, 0, now - window_sec)
        pipe.zcard(attempts)
        pipe.expire(attempts, window_sec)
        results = pipe.execute()
        return int(results[2])

    def lock(self, key: str, duration_sec: int) -> None:
        self._r.set(self._lock_key(key), "1", ex=duration_sec)  # type: ignore[attr-defined]

    def status(self, key: str, window_sec: int) -> tuple[int, int]:
        now = time.time()
        attempts = self._attempts_key(key)
        self._r.zremrangebyscore(attempts, 0, now - window_sec)  # type: ignore[attr-defined]
        count = int(self._r.zcard(attempts) or 0)  # type: ignore[attr-defined]
        ttl = int(self._r.ttl(self._lock_key(key)) or 0)  # type: ignore[attr-defined]
        return count, max(ttl, 0)

    def clear(self, key: str) -> None:
        self._r.delete(self._attempts_key(key), self._lock_key(key))  # type: ignore[attr-defined]


def _build_default_store() -> _LockoutStore:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return _InMemoryStore()
    try:
        import redis  # type: ignore[import-not-found]

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=0.25)
        client.ping()
        return _RedisStore(client)
    except Exception as exc:  # pragma: no cover - exercised manually
        _logger.warning(
            "account_lockout_redis_unavailable",
            error=str(exc),
            fallback="in_memory",
        )
        return _InMemoryStore()


class AccountLockoutTracker:
    """High-level API used by the auth flow.

    Always operate by ``(email, ip)`` tuple — never email-only — so a hostile
    network cannot lock a real user out of their account.
    """

    def __init__(
        self,
        *,
        store: _LockoutStore | None = None,
        max_fails: int | None = None,
        window_sec: int | None = None,
        lock_duration_sec: int | None = None,
    ) -> None:
        self.store = store or _build_default_store()
        self.max_fails = max_fails or _env_int("ACCOUNT_LOCKOUT_MAX_FAILS", 5)
        self.window_sec = window_sec or _env_int("ACCOUNT_LOCKOUT_WINDOW_SEC", 15 * 60)
        self.lock_duration_sec = lock_duration_sec or _env_int(
            "ACCOUNT_LOCKOUT_DURATION_SEC", 30 * 60
        )

    @staticmethod
    def _key(email: str, ip: str) -> str:
        email_norm = (email or "").strip().lower()
        ip_norm = (ip or "unknown").strip().lower()
        return f"{email_norm}|{ip_norm}"

    def check(self, email: str, ip: str) -> LockoutStatus:
        key = self._key(email, ip)
        failed, retry_after = self.store.status(key, self.window_sec)
        return LockoutStatus(
            locked=retry_after > 0,
            failed_count=failed,
            retry_after_seconds=retry_after,
        )

    def record_failure(self, email: str, ip: str) -> LockoutStatus:
        key = self._key(email, ip)
        failed = self.store.record_failure(key, self.window_sec)
        if failed >= self.max_fails:
            self.store.lock(key, self.lock_duration_sec)
            _logger.warning(
                "account_locked",
                email=email,
                ip=ip,
                fails=failed,
                duration_sec=self.lock_duration_sec,
            )
            return LockoutStatus(
                locked=True,
                failed_count=failed,
                retry_after_seconds=self.lock_duration_sec,
            )
        return LockoutStatus(locked=False, failed_count=failed, retry_after_seconds=0)

    def record_success(self, email: str, ip: str) -> None:
        self.store.clear(self._key(email, ip))

    def unlock(self, email: str, ip: str) -> None:
        self.store.clear(self._key(email, ip))

    def unlock_all_ips_for_email(self, email: str, ips: Iterable[str]) -> None:
        for ip in ips:
            self.store.clear(self._key(email, ip))


_default_tracker: AccountLockoutTracker | None = None
_default_lock = threading.Lock()


def get_default_tracker() -> AccountLockoutTracker:
    global _default_tracker
    if _default_tracker is None:
        with _default_lock:
            if _default_tracker is None:
                _default_tracker = AccountLockoutTracker()
    return _default_tracker


def reset_default_tracker() -> None:
    """Test hook — drop the cached tracker so env changes are re-read."""

    global _default_tracker
    with _default_lock:
        _default_tracker = None
