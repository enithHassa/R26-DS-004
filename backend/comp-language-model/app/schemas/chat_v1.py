"""Multi-turn conversational tax advisory API (FR9 MVP)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.proof_map_v1 import ProofMap
from app.schemas.query_v1 import QueryResponse


class ChatMessageIn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = Field(
        default=None,
        description="Existing session id; omit to start a new conversation.",
    )
    top_k: int | None = Field(default=None, ge=1, le=50)
    synthesize_answer: bool = Field(default=True)
    assessment_year_hint: str | None = Field(
        default=None,
        description="Optional YYYY_YY assessment year for symbolic validation.",
    )
    profile_id: str | None = Field(
        default=None,
        description=(
            "Caller's own financial_profiles.id (UUID). Required to answer questions "
            "about the caller's specific taxpayer details; the chat never returns another "
            "taxpayer's data."
        ),
    )
    user_id: str | None = Field(
        default=None,
        description=(
            "Caller's users.id (UUID). When present and chat history is enabled, the "
            "conversation is persisted to the DB under this user and can be listed / "
            "resumed later. Sessions are strictly per-user."
        ),
    )


class TaxpayerContext(BaseModel):
    """Transparency block describing the taxpayer grounding used for this turn."""

    used: bool = False
    profile_id: str | None = None
    taxpayer_name: str | None = None
    tax_year: str | None = None
    fields_used: list[str] = Field(default_factory=list)
    context_sources: list[str] = Field(
        default_factory=list,
        description="Intent-routed system data sources selected for this turn.",
    )
    kg_consistency: str | None = None
    note: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    turn_index: int
    user_message: str
    assistant_message: str | None = None
    query_result: QueryResponse
    proof_map: ProofMap | None = None
    history_length: int = 0
    taxpayer_context: TaxpayerContext | None = None
    persisted: bool = Field(
        default=False,
        description="True when this turn was saved to the per-user DB history.",
    )


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str | None = None
    archived: bool = False
    created_at: str
    last_message_at: str
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    user_id: str
    sessions: list[ChatSessionSummary]


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    created_at: str
    query_result: QueryResponse | None = None
    proof_map: ProofMap | None = None
    taxpayer_context: TaxpayerContext | None = None


class ChatSessionDetailResponse(BaseModel):
    session_id: str
    title: str | None = None
    archived: bool = False
    created_at: str
    last_message_at: str
    messages: list[ChatHistoryMessage]


class ChatSessionPatchRequest(BaseModel):
    user_id: str = Field(..., description="Caller's users.id (UUID). Must own the session.")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None
