"""Alembic environment configuration for async SQLAlchemy migrations.

Run migrations:
    alembic upgrade head

Create a new migration:
    alembic revision --autogenerate -m "describe your change"
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect schema changes
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402, F401
    Clip,
    Snippet,
    Space,
    Team,
    TeamMember,
    Todo,
    User,
)

target_metadata = Base.metadata


def get_url() -> str:
    """Reads the database URL from app settings (overrides alembic.ini)."""
    from app.config import settings

    return settings.database_url


def run_migrations_offline() -> None:
    """Runs migrations in 'offline' mode (no live DB connection required).

    Useful for generating SQL scripts to review before applying.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Runs migrations within a synchronous connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Runs migrations using an async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
