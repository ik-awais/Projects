# backend/app/db/base.py

"""
SQLAlchemy declarative base and shared mixins.
Every ORM model in app/models/ must inherit from Base.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp factory, used as a default for
    created_at/updated_at columns instead of naive datetime.utcnow()."""
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    """Mixin providing a UUID primary key generated client-side, so the
    ID is available immediately after object construction without a
    round trip to the database."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Mixin providing created_at/updated_at columns with timezone-aware
    UTC defaults. updated_at is refreshed automatically on every UPDATE."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )