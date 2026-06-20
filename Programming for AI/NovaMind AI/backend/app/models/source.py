# backend/app/models/source.py

"""
Source ORM model.
Stores the web sources cited in a specific assistant message — one row
per cited source, ordered by their citation position (e.g. [1], [2], [3]
in the rendered answer).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class Source(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sources"

    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    message: Mapped["Message"] = relationship(
        "Message",
        back_populates="sources",
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} message_id={self.message_id} position={self.position} domain={self.domain!r}>"