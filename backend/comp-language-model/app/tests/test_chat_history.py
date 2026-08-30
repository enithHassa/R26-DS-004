"""Per-user chat history persistence + isolation (FR9)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.chat_history import LlmChatMessage, LlmChatSession
from app.services.chat_history_store import ChatHistoryStore
from backend.shared.auth.models import User  # noqa: F401 -- makes `users` resolvable for FK


@pytest.fixture()
def store() -> ChatHistoryStore:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    LlmChatSession.metadata.create_all(
        bind=engine,
        tables=[User.__table__, LlmChatSession.__table__, LlmChatMessage.__table__],
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    s = ChatHistoryStore(session_factory=factory)
    return s


def test_create_append_and_resume(store: ChatHistoryStore) -> None:
    user = str(uuid.uuid4())
    sid = store.create_session(user)
    assert sid

    assert store.append_message(sid, user, "user", "What is personal relief for 2025/26?")
    assert store.append_message(sid, user, "assistant", "It is LKR 3,000,000.", payload={"query_result": {"x": 1}})
    assert store.append_message(sid, user, "user", "And for 2024/25?")

    detail = store.get_session_detail(sid, user)
    assert detail is not None
    assert [m.role for m in detail.messages] == ["user", "assistant", "user"]
    assert detail.messages[1].payload == {"query_result": {"x": 1}}
    # title derived from first user turn
    assert detail.title.startswith("What is personal relief")

    # resume context = recent user turns
    assert store.recent_turns_text(sid, user) == [
        "What is personal relief for 2025/26?",
        "And for 2024/25?",
    ]


def test_sessions_are_per_user(store: ChatHistoryStore) -> None:
    alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
    a_sid = store.create_session(alice)
    store.append_message(a_sid, alice, "user", "alice private question")
    b_sid = store.create_session(bob)
    store.append_message(b_sid, bob, "user", "bob private question")

    # Bob cannot read, resume, rename or delete Alice's session.
    assert store.get_session_detail(a_sid, bob) is None
    assert store.recent_turns_text(a_sid, bob) == []
    assert store.rename_session(a_sid, bob, "hijack") is False
    assert store.delete_session(a_sid, bob) is False
    assert store.append_message(a_sid, bob, "user", "injected") is False

    # Each user only lists their own.
    assert [s.session_id for s in store.list_sessions(alice)] == [a_sid]
    assert [s.session_id for s in store.list_sessions(bob)] == [b_sid]

    # Owner still has full access.
    assert store.get_session_detail(a_sid, alice) is not None


def test_list_ordering_archive_and_delete(store: ChatHistoryStore) -> None:
    user = str(uuid.uuid4())
    s1 = store.create_session(user)
    store.append_message(s1, user, "user", "first")
    s2 = store.create_session(user)
    store.append_message(s2, user, "user", "second")
    # s2 touched most recently → comes first
    assert [s.session_id for s in store.list_sessions(user)] == [s2, s1]

    assert store.set_archived(s2, user, True)
    assert [s.session_id for s in store.list_sessions(user)] == [s1]
    assert [s.session_id for s in store.list_sessions(user, include_archived=True)] == [s2, s1]

    assert store.delete_session(s1, user)
    assert store.get_session_detail(s1, user) is None


def test_bad_ids_are_safe(store: ChatHistoryStore) -> None:
    assert store.create_session("not-a-uuid") is None
    assert store.get_session_detail("not-a-uuid", str(uuid.uuid4())) is None
    assert store.append_message(str(uuid.uuid4()), "nope", "user", "x") is False
    assert store.list_sessions("nope") == []
