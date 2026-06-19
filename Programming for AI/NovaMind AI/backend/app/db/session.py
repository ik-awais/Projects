# backend/app/db/session.py

"""
Async SQLAlchemy engine and session factory.
This is the single source of database connectivity for the application —
no other module should call create_async_engine directly.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession scoped to a single
    request. Commits on clean exit, rolls back on exception, always
    closes the session afterward.

    Usage in routes:
        async def endpoint(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context-manager equivalent of get_db_session, for use outside of
    FastAPI's dependency injection — e.g. inside background workers,
    startup scripts, or the search pipeline's internal persistence calls.

    Usage:
        async with get_db_session_context() as db:
            ...
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Cleanly dispose of the engine's connection pool. Called from the
    FastAPI app's shutdown lifecycle in main.py."""
    await engine.dispose()