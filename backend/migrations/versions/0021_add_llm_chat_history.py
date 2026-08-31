"""Persistent per-user LLM chat history (Component 4, FR9).

Revision ID: 0021_add_llm_chat_history
Revises: 0020_add_user_transaction_flags
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_add_llm_chat_history"
down_revision: str | None = "0020_add_user_transaction_flags"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "archived", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_chat_sessions_user_id", "llm_chat_sessions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_llm_chat_sessions_user_last_msg",
        "llm_chat_sessions",
        ["user_id", "last_message_at"],
        unique=False,
    )

    op.create_table(
        "llm_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["llm_chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_llm_chat_messages_session_id",
        "llm_chat_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_llm_chat_messages_session_ordinal",
        "llm_chat_messages",
        ["session_id", "ordinal"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_chat_messages_session_ordinal", table_name="llm_chat_messages")
    op.drop_index("ix_llm_chat_messages_session_id", table_name="llm_chat_messages")
    op.drop_table("llm_chat_messages")
    op.drop_index("ix_llm_chat_sessions_user_last_msg", table_name="llm_chat_sessions")
    op.drop_index("ix_llm_chat_sessions_user_id", table_name="llm_chat_sessions")
    op.drop_table("llm_chat_sessions")
