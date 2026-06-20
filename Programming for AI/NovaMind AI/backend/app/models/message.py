# backend/app/models/message.py  (corrected — replaces the version above)

"""
Message ORM model.
Each message belongs to exactly one conversation and represents a single
turn (user question or assistant answer) in that thread. Assistant
messages may have associated Source records (citations) and Search
records (the search execution that produced the answer).

Messages are immutable once created (no updated_at) — a corrected or
follow-up answer is a new message, not an edit of an existing one.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(
            MessageRole,
            name="message_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    sources: Mapped[list["Source"]] = relationship(
        "Source",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="Source.position",
        lazy="selectin",
    )
    searches: Mapped[list["Search"]] = relationship(
        "Search",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id} role={self.role.value}>"