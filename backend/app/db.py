from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.models.base import Base  # re-exported for callers
from app.utils.logging import get_logger

__all__ = ["Base", "engine", "AsyncSessionLocal", "get_db", "_make_engine"]


_logger = get_logger(__name__)


def _build_engine_kwargs(database_url: str) -> dict[str, object]:
    """Compute create_async_engine kwargs for the given URL.

    SQLite uses StaticPool for in-memory portability; Postgres uses the
    tunable connection pool configured via DB_POOL_* env vars (see
    app/config.py).
    """

    kwargs: dict[str, object] = {"echo": False, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["pool_pre_ping"] = True
        if ":memory:" in database_url or database_url.endswith("://"):
            kwargs["poolclass"] = StaticPool
        return kwargs

    # Postgres / other server-side databases: apply tuned pool settings.
    kwargs["pool_size"] = settings.db_pool_size
    kwargs["max_overflow"] = settings.db_max_overflow
    kwargs["pool_timeout"] = settings.db_pool_timeout_sec
    kwargs["pool_recycle"] = settings.db_pool_recycle_sec
    kwargs["pool_pre_ping"] = settings.db_pool_pre_ping
    return kwargs


def _attach_statement_timeout(eng: AsyncEngine, database_url: str) -> None:
    """Apply per-connection statement_timeout on Postgres backends."""

    if not database_url.startswith("postgresql"):
        return
    timeout_ms = settings.db_statement_timeout_ms

    @event.listens_for(eng.sync_engine, "connect")
    def _set_statement_timeout(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f"SET statement_timeout = '{timeout_ms}ms'")
        finally:
            cur.close()


def _make_engine(database_url: str) -> AsyncEngine:
    """Build an AsyncEngine with backend-appropriate pool + listeners."""

    eng = create_async_engine(database_url, **_build_engine_kwargs(database_url))
    _attach_statement_timeout(eng, database_url)
    return eng


engine = _make_engine(settings.database_url)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession, commits on success, rolls back on error."""

    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        _logger.exception("db_session_rollback")
        raise
    finally:
        await session.close()

