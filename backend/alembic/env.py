from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure the backend package root (which contains the `app` package) is on
# sys.path regardless of where `alembic` is invoked from.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    """Return a sync SQLAlchemy URL by stripping async driver suffixes."""
    url = settings.database_url
    for async_suffix, sync_suffix in (
        ("postgresql+asyncpg", "postgresql+psycopg2"),
        ("postgresql+psycopg", "postgresql+psycopg2"),
        ("sqlite+aiosqlite", "sqlite"),
        ("mysql+aiomysql", "mysql+pymysql"),
    ):
        if url.startswith(async_suffix + "://"):
            return sync_suffix + url[len(async_suffix):]
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live DB)."""
    url = _sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a synchronous Engine."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
