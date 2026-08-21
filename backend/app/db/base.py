"""SQLAlchemy declarative base class.

All ORM models inherit from this Base class. It provides:
- A shared metadata registry for all tables
- Automatic table name generation from class names
- A place to add common columns (created_at, updated_at) via mixins

Why a separate base.py?
- Avoids circular imports: models import Base, but Base doesn't import models
- Single source of truth for the metadata Alembic uses for migrations
- Clean place to add shared model behaviors (mixins, naming conventions)
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Provides common timestamp columns that every table should have.
    Subclasses automatically get 'created_at' and 'updated_at' columns.
    """
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns.

    Usage:
        class User(TimestampMixin, Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)

    The created_at is set once on INSERT (via server_default).
    The updated_at is updated on every UPDATE (via onupdate).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
