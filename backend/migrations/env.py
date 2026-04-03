"""Alembic environment configuration for PhishTrack.

Supports both async (PostgreSQL) and sync (SQLite) database drivers.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

from alembic import context

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings and models
from app.config import settings
from app.database import Base

# Import all models to ensure they are registered with Base.metadata
from app.models import (  # noqa: F401
    Role, User, UserSession, AuditLog, Case, HistoricalCase, EmailTemplate,
    Evidence, GeneratedReport, PublicSubmission,
    BlacklistSource, BlacklistDomain, WhitelistEntry
)

# Alembic Config object
config = context.config

# Set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL script(s) instead of running against a live database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Detect column type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Create async engine
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Detects if we're using an async driver and handles accordingly.
    """
    db_url = settings.DATABASE_URL
    
    # Check if using async driver
    is_async = "asyncpg" in db_url or ("sqlite" in db_url and "+" in db_url)
    
    if is_async:
        asyncio.run(run_async_migrations())
    else:
        # Sync mode for non-async drivers
        from sqlalchemy import create_engine
        
        connectable = create_engine(
            db_url,
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
