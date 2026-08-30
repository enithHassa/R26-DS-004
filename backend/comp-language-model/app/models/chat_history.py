"""Persistent, per-user multi-turn chat history (FR9).

Every session belongs to exactly one ``users.id``. All reads and writes in
``app.services.chat_history_store`` are filtered by ``user_id`` so a user can
only ever see or resume their own conversations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.shared.config.database import Base

# JSONB on Postgres, plain JSON elsewhere (sqlite in tests).
_JSON = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class LlmChatSession(Base):
    __tablename__ = "llm_chat_sessions"
    __table_args__ = (
        Index("ix_llm_chat_sessions_user_last_msg", "user_id", "last_message_at"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    messages: Mapped[list[LlmChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LlmChatMessage.ordinal",
    )


class LlmChatMessage(Base):
    __tablename__ = "llm_chat_messages"
    __table_args__ = (
        Index("ix_llm_chat_messages_session_ordinal", "session_id", "ordinal"),
        {"extend_existing": True},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("llm_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Monotonic position within the session — the authoritative message order
    # (created_at can tie at sub-second granularity within one request).
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Full response payload for an assistant turn (query_result, proof_map,
    # taxpayer_context) so a resumed conversation renders exactly as before.
    payload: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[LlmChatSession] = relationship(back_populates="messages")
