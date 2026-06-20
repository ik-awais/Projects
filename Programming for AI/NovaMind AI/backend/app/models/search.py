# backend/app/models/search.py

"""
Search ORM model.
Stores metadata about a single search-provider execution that fed into an
assistant message — used for auditing, latency analysis, and provider
performance comparison (Tavily vs Brave) per the approved search router
architecture. One Message may have multiple Search records if multiple
providers or sub-queries were used (e.g. deep research mode).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class Search(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "searches"

    message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    search_time_ms: Mapped[int] = mapped_column(
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
        back_populates="searches",
    )

    def __repr__(self) -> str:
        return f"<Search id={self.id} message_id={self.message_id} provider={self.provider!r} time_ms={self.search_time_ms}>"