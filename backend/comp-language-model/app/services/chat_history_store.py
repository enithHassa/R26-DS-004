"""DB-backed, per-user chat history.

Replaces the in-memory :class:`ChatSessionStore` when a ``user_id`` is present
on the request. Every method takes ``user_id`` and filters by it, so a user can
only read, resume, rename or delete their own conversations — a session id that
belongs to another user is treated as "not found".
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.chat_history import LlmChatMessage, LlmChatSession
from backend.shared.config.database import SessionLocal, engine
from backend.shared.utils.logging import logger

_TABLES_READY = False


def ensure_tables() -> None:
    """Create the two chat tables if missing (idempotent self-heal).

    ``alembic upgrade head`` (migration 0021) is the blessed path; this guard
    just means the feature also works on a fresh DB that has not been migrated
    yet. A read-only DB role simply logs a warning and history stays disabled.
    """
    global _TABLES_READY
    if _TABLES_READY:
        return
    try:
        LlmChatSession.metadata.create_all(
            bind=engine,
            tables=[LlmChatSession.__table__, LlmChatMessage.__table__],
            checkfirst=True,
        )
        _TABLES_READY = True
    except Exception as exc:  # pragma: no cover - depends on DB perms
        logger.warning("Could not ensure llm_chat_* tables exist: {}", exc)


def _valid_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


@dataclass(slots=True)
class SessionSummary:
    session_id: str
    title: str | None
    archived: bool
    created_at: str
    last_message_at: str
    message_count: int


@dataclass(slots=True)
class HistoryMessage:
    role: str
    content: str
    created_at: str
    payload: dict[str, Any] | None


@dataclass(slots=True)
class SessionDetail:
    session_id: str
    title: str | None
    archived: bool
    created_at: str
    last_message_at: str
    messages: list[HistoryMessage]


def _iso(dt: datetime | None) -> str:
    return (dt or datetime.now(UTC)).isoformat()


class ChatHistoryStore:
    """User-scoped persistence for chat sessions and messages."""

    def __init__(self, session_factory: Callable[[], Session] | sessionmaker = SessionLocal) -> None:
        self._session_factory = session_factory
        ensure_tables()

    # -- internal -----------------------------------------------------------
    def _owned_session(self, db: Session, session_id: str, user_id: uuid.UUID) -> LlmChatSession | None:
        sid = _valid_uuid(session_id)
        if sid is None:
            return None
        return db.execute(
            select(LlmChatSession).where(
                LlmChatSession.id == sid, LlmChatSession.user_id == user_id
            )
        ).scalar_one_or_none()

    # -- writes -----------------------------------------------------------
    def create_session(self, user_id: str, *, title: str | None = None) -> str | None:
        uid = _valid_uuid(user_id)
        if uid is None:
            return None
        with self._session_factory() as db:
            row = LlmChatSession(user_id=uid, title=(title or None))
            db.add(row)
            db.commit()
            return str(row.id)

    def append_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        uid = _valid_uuid(user_id)
        if uid is None:
            return False
        with self._session_factory() as db:
            session = self._owned_session(db, session_id, uid)
            if session is None:
                return False
            next_ordinal = (
                db.execute(
                    select(func.coalesce(func.max(LlmChatMessage.ordinal), -1)).where(
                        LlmChatMessage.session_id == session.id
                    )
                ).scalar_one()
                + 1
            )
            db.add(
                LlmChatMessage(
                    session_id=session.id,
                    ordinal=next_ordinal,
                    role=role,
                    content=content,
                    payload=payload,
                )
            )
            session.last_message_at = datetime.now(UTC)
            if role == "user" and not session.title:
                session.title = content.strip()[:200]
            db.commit()
            return True

    def rename_session(self, session_id: str, user_id: str, title: str) -> bool:
        uid = _valid_uuid(user_id)
        if uid is None:
            return False
        with self._session_factory() as db:
            session = self._owned_session(db, session_id, uid)
            if session is None:
                return False
            session.title = title.strip()[:200] or None
            db.commit()
            return True

    def set_archived(self, session_id: str, user_id: str, archived: bool) -> bool:
        uid = _valid_uuid(user_id)
        if uid is None:
            return False
        with self._session_factory() as db:
            session = self._owned_session(db, session_id, uid)
            if session is None:
                return False
            session.archived = archived
            db.commit()
            return True

    def delete_session(self, session_id: str, user_id: str) -> bool:
        uid = _valid_uuid(user_id)
        if uid is None:
            return False
        with self._session_factory() as db:
            session = self._owned_session(db, session_id, uid)
            if session is None:
                return False
            db.execute(delete(LlmChatSession).where(LlmChatSession.id == session.id))
            db.commit()
            return True

    # -- reads -----------------------------------------------------------
    def list_sessions(
        self, user_id: str, *, limit: int = 100, include_archived: bool = False
    ) -> list[SessionSummary]:
        uid = _valid_uuid(user_id)
        if uid is None:
            return []
        count_sq = (
            select(
                LlmChatMessage.session_id,
                func.count(LlmChatMessage.id).label("n"),
            )
            .group_by(LlmChatMessage.session_id)
            .subquery()
        )
        stmt = (
            select(LlmChatSession, func.coalesce(count_sq.c.n, 0))
            .outerjoin(count_sq, count_sq.c.session_id == LlmChatSession.id)
            .where(LlmChatSession.user_id == uid)
            .order_by(LlmChatSession.last_message_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        if not include_archived:
            stmt = stmt.where(LlmChatSession.archived.is_(False))
        with self._session_factory() as db:
            rows = db.execute(stmt).all()
        return [
            SessionSummary(
                session_id=str(s.id),
                title=s.title,
                archived=s.archived,
                created_at=_iso(s.created_at),
                last_message_at=_iso(s.last_message_at),
                message_count=int(n),
            )
            for s, n in rows
        ]

    def get_session_detail(self, session_id: str, user_id: str) -> SessionDetail | None:
        uid = _valid_uuid(user_id)
        if uid is None:
            return None
        with self._session_factory() as db:
            session = self._owned_session(db, session_id, uid)
            if session is None:
                return None
            msgs = db.execute(
                select(LlmChatMessage)
                .where(LlmChatMessage.session_id == session.id)
                .order_by(LlmChatMessage.ordinal)
            ).scalars().all()
            return SessionDetail(
                session_id=str(session.id),
                title=session.title,
                archived=session.archived,
                created_at=_iso(session.created_at),
                last_message_at=_iso(session.last_message_at),
                messages=[
                    HistoryMessage(
                        role=m.role,
                        content=m.content,
                        created_at=_iso(m.created_at),
                        payload=m.payload,
                    )
                    for m in msgs
                ],
            )

    def recent_turns_text(self, session_id: str, user_id: str, *, max_user_turns: int = 4) -> list[str]:
        """Recent user-turn contents, oldest→newest, for follow-up retrieval context."""
        detail = self.get_session_detail(session_id, user_id)
        if detail is None:
            return []
        return [m.content for m in detail.messages if m.role == "user"][-max_user_turns:]
