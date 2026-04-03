"""Database connection and session management for PhishTrack."""
import os
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create sync engine for Celery tasks (convert async driver URLs to sync)
def _get_sync_database_url(async_url: str) -> str:
    """Convert async database URL to sync URL."""
    # Handle SQLite: sqlite+aiosqlite:/// -> sqlite:/// (generic async driver detection)
    if "sqlite+" in async_url:
        return async_url.split("+", 1)[0] + "://" + async_url.split("://", 1)[1]
    # Handle PostgreSQL: postgresql+asyncpg:// -> postgresql://
    if "postgresql+asyncpg://" in async_url:
        return async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    # If no async driver specified, return as-is
    return async_url

sync_engine = create_engine(
    _get_sync_database_url(settings.DATABASE_URL),
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create sync session factory for Celery tasks
sync_session_factory = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for use in async context managers.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and seed default data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run automatic migrations for schema changes
    await run_migrations()

    # Seed default roles and admin user
    try:
        await seed_default_data()
    except Exception as e:
        print(f"Warning: Database seeding failed: {e}")
        # Don't fail startup if seeding fails


async def run_migrations() -> None:
    """Run automatic migrations for schema changes.

    This function handles incremental schema updates that can't be
    handled by SQLAlchemy's create_all (which only adds new tables).
    """
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        # Migration: Add html_body column to email_templates if missing
        def get_columnsInspector(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_columns('email_templates')

        try:
            columns = await conn.run_sync(get_columnsInspector)
            column_names = [col['name'] for col in columns]

            # Migration: Add html_body column to email_templates if missing
            if 'html_body' not in column_names:
                print("Migration: Adding html_body column to email_templates table...")
                await conn.execute(text("""
                    ALTER TABLE email_templates
                    ADD COLUMN html_body TEXT
                """))
                print("Migration: html_body column added successfully.")
            else:
                print("Database schema up to date (html_body column exists).")

        except Exception as e:
            # Table might not exist yet (fresh install)
            print(f"Migration check skipped: {e}")

        # Migration: Create user_sessions table if missing
        def get_table_list(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()

        try:
            tables = await conn.run_sync(get_table_list)

            if 'user_sessions' not in tables:
                print("Migration: Creating user_sessions table...")
                await conn.execute(text("""
                    CREATE TABLE user_sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        token_hash VARCHAR(64) NOT NULL,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX ix_user_sessions_user_id ON user_sessions(user_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX ix_user_sessions_token_hash ON user_sessions(token_hash)
                """))
                await conn.execute(text("""
                    CREATE INDEX ix_user_sessions_expires_at ON user_sessions(expires_at)
                """))
                await conn.execute(text("""
                    CREATE INDEX ix_user_sessions_is_active ON user_sessions(is_active)
                """))
                print("Migration: user_sessions table created successfully.")
            else:
                print("Database schema up to date (user_sessions table exists).")

        except Exception as e:
            print(f"User sessions migration check skipped: {e}")

        # Migration: Make brand_impacted nullable in cases table
        def get_cases_columns(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_columns('cases')

        try:
            columns = await conn.run_sync(get_cases_columns)
            brand_impacted_col = next((c for c in columns if c['name'] == 'brand_impacted'), None)

            if brand_impacted_col and not brand_impacted_col.get('nullable'):
                print("Migration: Making brand_impacted column nullable in cases table...")
                # First, update any NULL values to 'Unknown'
                await conn.execute(text("""
                    UPDATE cases SET brand_impacted = 'Unknown' WHERE brand_impacted IS NULL
                """))
                # Then make the column nullable
                await conn.execute(text("""
                    ALTER TABLE cases ALTER COLUMN brand_impacted DROP NOT NULL
                """))
                print("Migration: brand_impacted column is now nullable.")
            else:
                print("Database schema up to date (brand_impacted is nullable).")

        except Exception as e:
            print(f"Brand impacted migration check skipped: {e}")

        # Migration: Add reported_by column to historical_cases table
        def get_historical_cases_columns(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_columns('historical_cases')

        try:
            columns = await conn.run_sync(get_historical_cases_columns)
            column_names = [col['name'] for col in columns]

            if 'reported_by' not in column_names:
                print("Migration: Adding reported_by column to historical_cases table...")
                await conn.execute(text("""
                    ALTER TABLE historical_cases
                    ADD COLUMN reported_by VARCHAR(36)
                """))
                await conn.execute(text("""
                    CREATE INDEX ix_historical_cases_reported_by ON historical_cases(reported_by)
                """))
                print("Migration: reported_by column added successfully.")
            else:
                print("Database schema up to date (reported_by column exists).")

        except Exception as e:
            print(f"Reported by migration check skipped: {e}")


async def seed_default_data() -> None:
    """Seed default roles and admin user if they don't exist.

    Idempotent - safe to run multiple times. Only creates data if missing.
    """
    from app.models import Role, User
    from app.auth.security import hash_password
    from app.permissions import ROLE_PERMISSIONS, ROLE_DESCRIPTIONS
    from app.utils.timezone import now_utc
    from sqlalchemy import select

    async with async_session_factory() as db:
        # Create default roles
        for role_name, permissions in ROLE_PERMISSIONS.items():
            existing = await db.execute(
                select(Role).where(Role.name == role_name)
            )
            if not existing.scalar_one_or_none():
                perm_list = [str(p.value) if hasattr(p, 'value') else str(p) for p in permissions]
                role = Role(
                    name=role_name,
                    description=ROLE_DESCRIPTIONS.get(role_name, ""),
                    permissions=perm_list,
                    created_at=now_utc(),
                )
                db.add(role)
                print(f"Created role: {role_name}")

        await db.commit()

        # Create default admin user if no users exist
        admin_role = await db.execute(
            select(Role).where(Role.name == "ADMIN")
        )
        admin_role = admin_role.scalar_one_or_none()

        if admin_role:
            existing_users = await db.execute(select(User).limit(1))
            if not existing_users.scalar_one_or_none():
                admin_user = User(
                    username="admin",
                    email="admin@phishtrack.dev",
                    hashed_password=hash_password(os.getenv("DEFAULT_ADMIN_PASSWORD", "changeme")),
                    role_id=str(admin_role.id),
                    is_active=True,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(admin_user)
                await db.commit()
                print("Default admin user created (username: admin)")
                print("[!] Password: Use DEFAULT_ADMIN_PASSWORD env var or change immediately")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def cleanup_expired_sessions() -> int:
    """Delete expired and inactive sessions from the database.

    This function should be called periodically (e.g., via a background task)
    to clean up old sessions.

    Returns:
        Number of sessions deleted
    """
    from sqlalchemy import delete, select, and_
    from app.models import UserSession
    from app.utils.timezone import now_utc

    async with async_session_factory() as db:
        # Delete sessions that are either expired or inactive
        current_time = now_utc()
        delete_stmt = delete(UserSession).where(
            and_(
                UserSession.expires_at < current_time,
                UserSession.is_active == False,
            )
        )
        result = await db.execute(delete_stmt)
        await db.commit()
        return result.rowcount


@contextmanager
def get_sync_db_context() -> Generator[Session, None, None]:
    """Get sync database session for use in sync context managers (Celery).

    Yields:
        Session: Synchronous database session
    """
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_sync_db() -> None:
    """Close sync database connections."""
    sync_engine.dispose()
