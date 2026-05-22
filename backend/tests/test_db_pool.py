"""Tests for the DB engine factory: pool sizing + statement_timeout listener.

The default test runtime uses in-memory SQLite (StaticPool); the Postgres
branch is exercised by inspecting the kwargs passed to
``create_async_engine`` so we don't need a live Postgres in CI.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool

from app import db as db_module
from app.config import Settings


def test_sqlite_memory_uses_static_pool() -> None:
    """In-memory SQLite must use StaticPool so all sessions share one conn."""

    kwargs = db_module._build_engine_kwargs("sqlite+aiosqlite:///:memory:")
    assert kwargs["poolclass"] is StaticPool
    assert kwargs["connect_args"] == {"check_same_thread": False}
    # SQLite branch must NOT carry the pg-only pool tuning kwargs.
    for forbidden in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
        assert forbidden not in kwargs, f"sqlite branch leaked {forbidden}"


def test_postgres_kwargs_carry_pool_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres URLs must propagate every db_pool_* / db_max_overflow setting."""

    monkeypatch.setattr(db_module.settings, "db_pool_size", 33)
    monkeypatch.setattr(db_module.settings, "db_max_overflow", 7)
    monkeypatch.setattr(db_module.settings, "db_pool_timeout_sec", 11.5)
    monkeypatch.setattr(db_module.settings, "db_pool_recycle_sec", 600)
    monkeypatch.setattr(db_module.settings, "db_pool_pre_ping", False)

    kwargs = db_module._build_engine_kwargs(
        "postgresql+asyncpg://u:p@host:5432/db"
    )
    assert kwargs["pool_size"] == 33
    assert kwargs["max_overflow"] == 7
    assert kwargs["pool_timeout"] == 11.5
    assert kwargs["pool_recycle"] == 600
    assert kwargs["pool_pre_ping"] is False
    assert "poolclass" not in kwargs  # let SA pick QueuePool default


def test_statement_timeout_listener_registered_only_for_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_attach_statement_timeout`` is a no-op on SQLite, active on PG."""

    fake_listens_for = MagicMock(return_value=lambda fn: fn)
    monkeypatch.setattr(db_module.event, "listens_for", fake_listens_for)

    # SQLite: must NOT register
    fake_engine = MagicMock()
    db_module._attach_statement_timeout(
        fake_engine, "sqlite+aiosqlite:///:memory:"
    )
    assert fake_listens_for.call_count == 0

    # Postgres: must register exactly once on (sync_engine, "connect")
    db_module._attach_statement_timeout(
        fake_engine, "postgresql+asyncpg://u:p@h:5432/d"
    )
    assert fake_listens_for.call_count == 1
    args, _ = fake_listens_for.call_args
    assert args[0] is fake_engine.sync_engine
    assert args[1] == "connect"


def test_db_pool_settings_pick_up_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh Settings() reads DB_POOL_* env vars."""

    monkeypatch.setenv("DB_POOL_SIZE", "55")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "13")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "5000")
    cfg: Any = Settings()
    assert cfg.db_pool_size == 55
    assert cfg.db_max_overflow == 13
    assert cfg.db_statement_timeout_ms == 5000
