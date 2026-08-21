"""Async database engine and session factory.

This module creates the SQLAlchemy async engine and session factory.
The engine manages the connection pool; the session factory creates
individual sessions for each request.

Key concepts:
- Engine: manages a POOL of database connections (created once at startup)
- Session: a single "conversation" with the database (created per request)
- expire_on_commit=False: CRITICAL for async — prevents lazy-load errors
  after commit. Without this, accessing an attribute after commit would
  try to issue a synchronous SQL query, which blocks the event loop.

Database drivers:
- SQLite:     aiosqlite (async wrapper around sqlite3)
- PostgreSQL: asyncpg (native async PostgreSQL driver)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()

# Create the async engine (one per application lifetime)
# The engine manages a pool of connections to the database
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL statements when debug=True
    future=True,
)

# Session factory — creates new AsyncSession instances
# expire_on_commit=False is CRITICAL for async to prevent lazy-load errors
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session per request.

    Uses 'yield' so FastAPI can manage the session lifecycle:
    1. Creates a session before the request handler runs
    2. Yields the session to the handler
    3. Commits on success, rolls back on exception
    4. Always closes the session (via async with)

    Usage in a route:
        @router.get("/items")
        async def get_items(db: Annotated[AsyncSession, Depends(get_db_session)]):
            ...

    Yields:
        An AsyncSession connected to the database.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
