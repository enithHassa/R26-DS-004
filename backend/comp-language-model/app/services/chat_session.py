"""In-memory multi-turn chat sessions (FR9 MVP)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ChatSession:
    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ChatSessionStore:
    """Simple process-local session store for development and demos."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}

    def create(self) -> ChatSession:
        session = ChatSession(session_id=str(uuid.uuid4()))
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def append(self, session_id: str, role: str, content: str) -> ChatSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.messages.append(ChatMessage(role=role, content=content))
        return session

    def clear(self) -> None:
        self._sessions.clear()

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
