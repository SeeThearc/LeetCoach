"""Global dependency injection providers.

This module defines FastAPI dependencies that are shared across
multiple routers. Dependencies are functions that FastAPI calls
automatically before your route handler runs.

Why centralize dependencies?
- DRY: avoid duplicating get_db, get_settings across every router
- Testability: override dependencies in tests with app.dependency_overrides
- Composability: chain dependencies (service depends on repository depends on db)

Dependency Injection pattern:
  Route handler
    → depends on Service
      → depends on Repository
        → depends on AsyncSession
          → depends on get_db_session()

This is Constructor Injection — each layer receives its dependencies
through function parameters, not global imports.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session

# Type aliases for common dependencies
# Use these in route handlers for cleaner signatures:
#   async def get_items(db: DbSession, settings: AppSettings):

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
"""Annotated type alias for injecting database sessions."""

AppSettings = Annotated[Settings, Depends(get_settings)]
"""Annotated type alias for injecting application settings."""
