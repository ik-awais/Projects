# backend/app/db/migrations/env.py

"""
Alembic migration environment.

Runs migrations using a synchronous psycopg-style driver derived from the
application's async DATABASE_URL, since Alembic's autogenerate and DDL
execution machinery is synchronous. The async engine in app/db/session.py
is unaffected by this — it is used exclusively by the running application,
never by Alembic.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# Import every model module so its table registers on Base.metadata before
# Alembic compares it against the database for autogenerate. Each future
# model file must be added here when it is created.
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.user import User  # noqa: F401

# Alembic Config object, provides access to values within alembic.ini
config = context.config

# Interpret the config file for Python logging, per alembic.ini's [loggers]
# section. This sets up Alembic's own log formatting.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata used for 'autogenerate' support. Alembic diffs this
# against the live database schema to propose migration operations.
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Returns the application's DATABASE_URL unchanged. The URL already uses
    the asyncpg driver (postgresql+asyncpg://...), which this module runs
    through SQLAlchemy's async engine + run_sync bridge below, so no driver
    substitution is needed.
    """
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode: emits SQL to stdout/a script without
    a live database connection. Used for generating SQL review files in
    CI/CD pipelines rather than executing directly.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using an async engine, bridging to
    Alembic's synchronous migration runner via run_sync.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()