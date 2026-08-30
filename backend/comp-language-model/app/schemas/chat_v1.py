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


class ChatResponse(BaseModel):
    session_id: str
    turn_index: int
    user_message: str
    assistant_message: str | None = None
    query_result: QueryResponse
    proof_map: ProofMap | None = None
    history_length: int = 0
