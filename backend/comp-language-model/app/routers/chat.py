"""Multi-turn conversational tax advisory (FR9 MVP)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import get_lm_settings
from app.schemas.chat_v1 import ChatRequest, ChatResponse
from app.services.query_pipeline import run_query_pipeline

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class SuggestRequest(BaseModel):
    question: str
    answer: str


class SuggestResponse(BaseModel):
    suggestions: list[str]

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _contextual_question(session_messages: list, new_message: str, max_turns: int = 4) -> str:
    """Combine recent user turns with the latest message for retrieval."""
    user_turns = [m.content for m in session_messages if m.role == "user"][-max_turns:]
    if not user_turns:
        return new_message
    if len(user_turns) == 1 and user_turns[0] == new_message:
        return new_message
    prior = " ".join(user_turns[:-1]) if user_turns[-1] == new_message else " ".join(user_turns)
    if prior.strip():
        return f"{prior.strip()} Follow-up: {new_message.strip()}"
    return new_message.strip()


@router.post("", response_model=ChatResponse)
async def chat_turn(request: Request, body: ChatRequest) -> ChatResponse:
    store = getattr(request.app.state, "chat_session_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Chat session store unavailable")

    settings = get_lm_settings()
    session = store.get(body.session_id) if body.session_id else None
    if session is None:
        session = store.create()

    store.append(session.session_id, "user", body.message)

    # Domain gate runs on the raw new message only — not combined context —
    # so off-topic questions are rejected even inside a tax-heavy session.
    # Retrieval uses the contextual question for better follow-up recall.
    contextual = _contextual_question(session.messages, body.message)

    pipeline = await run_query_pipeline(
        request,
        settings,
        question=body.message,          # domain gate sees only new message
        retrieval_question=contextual,  # retrieval uses full context
        top_k=body.top_k,
        synthesize_answer=body.synthesize_answer,
        assessment_year_hint=body.assessment_year_hint,
        include_proof_map=True,
    )
    query_result = pipeline.response
    if pipeline.proof_map is not None:
        query_result.proof_map = pipeline.proof_map

    assistant_text = query_result.plain_answer
    if not assistant_text and query_result.citations:
        assistant_text = (
            "I found relevant legal passages but no synthesized summary was requested or available. "
            "See citations in the response payload."
        )
    if not assistant_text and query_result.domain_message:
        assistant_text = query_result.domain_message
    if not assistant_text:
        assistant_text = "I could not find grounded legal sources for that question."

    store.append(session.session_id, "assistant", assistant_text)
    updated = store.get(session.session_id)
    history_len = len(updated.messages) if updated else 0

    return ChatResponse(
        session_id=session.session_id,
        turn_index=history_len // 2,
        user_message=body.message,
        assistant_message=assistant_text,
        query_result=query_result,
        proof_map=query_result.proof_map,
        history_length=history_len,
    )


@router.post("/suggestions", response_model=SuggestResponse)
async def suggest_questions(body: SuggestRequest) -> SuggestResponse:
    """Generate 3 follow-up questions based on the last Q&A using Gemini."""
    settings = get_lm_settings()
    fallback = SuggestResponse(suggestions=[])

    if not settings.COMP_LLM_GEMINI_API_KEY:
        return fallback

    prompt = (
        "You are a Sri Lankan income tax assistant.\n"
        "A user just asked the following question and received this answer.\n\n"
        f"User question: {body.question}\n\n"
        f"Answer given: {body.answer}\n\n"
        "Suggest exactly 3 short follow-up questions the user might want to ask next, "
        "based on this topic. Each question must be about Sri Lankan income tax. "
        "Return ONLY the 3 questions, one per line, no numbering, no extra text."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000},
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                _GEMINI_URL.format(model=settings.COMP_LLM_GEMINI_MODEL),
                params={"key": settings.COMP_LLM_GEMINI_API_KEY},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        questions = [q.strip() for q in text.splitlines() if q.strip()][:3]
        return SuggestResponse(suggestions=questions)
    except Exception:
        return fallback


@router.delete("/sessions/{session_id}")
async def clear_chat_session(request: Request, session_id: str) -> dict[str, str]:
    store = getattr(request.app.state, "chat_session_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Chat session store unavailable")
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    store.delete(session_id)
    return {"status": "deleted", "session_id": session_id}
