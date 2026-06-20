# backend/app/db/migrations/versions/0003_sources_searches.py

"""create sources and searches tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-20 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_sources_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )
    op.create_index(
        op.f("ix_sources_message_id"), "sources", ["message_id"], unique=False
    )
    op.create_index(
        op.f("ix_sources_domain"), "sources", ["domain"], unique=False
    )

    op.create_table(
        "searches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(length=1000), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("search_time_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_searches_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_searches")),
    )
    op.create_index(
        op.f("ix_searches_message_id"), "searches", ["message_id"], unique=False
    )
    op.create_index(
        op.f("ix_searches_provider"), "searches", ["provider"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_searches_provider"), table_name="searches")
    op.drop_index(op.f("ix_searches_message_id"), table_name="searches")
    op.drop_table("searches")

    op.drop_index(op.f("ix_sources_domain"), table_name="sources")
    op.drop_index(op.f("ix_sources_message_id"), table_name="sources")
    op.drop_table("sources")