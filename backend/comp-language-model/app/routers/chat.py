"""Multi-turn conversational tax advisory (FR9).

Sessions persist to the shared DB, scoped per user, when the request carries
``user_id`` and ``COMP_LLM_CHAT_HISTORY_ENABLED`` is on. Otherwise an in-memory
process-local store is used (anonymous / demo mode).
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.config import get_lm_settings
from app.schemas.chat_v1 import (
    ChatHistoryMessage,
    ChatRequest,
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionPatchRequest,
    ChatSessionSummary,
    TaxpayerContext,
)
from app.schemas.proof_map_v1 import ProofMap
from app.schemas.query_v1 import QueryResponse
from app.services.query_pipeline import run_query_pipeline
from app.services.taxpayer_answer import answer_taxpayer_turn
from app.services.taxpayer_data import looks_taxpayer_specific

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class SuggestRequest(BaseModel):
    question: str
    answer: str


class SuggestResponse(BaseModel):
    suggestions: list[str]


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _contextual_from_turns(prior_user_turns: list[str], new_message: str, max_turns: int = 4) -> str:
    """Combine recent user turns with the latest message for retrieval recall."""
    turns = [t for t in prior_user_turns if t][-max_turns:]
    # drop the just-appended copy of the new message if present
    if turns and turns[-1] == new_message:
        turns = turns[:-1]
    prior = " ".join(t.strip() for t in turns if t.strip())
    if prior:
        return f"{prior} Follow-up: {new_message.strip()}"
    return new_message.strip()


def _contextual_question(session_messages: list, new_message: str, max_turns: int = 4) -> str:
    user_turns = [m.content for m in session_messages if m.role == "user"]
    return _contextual_from_turns(user_turns, new_message, max_turns)


def _assistant_payload(query_result: QueryResponse, taxpayer_ctx: TaxpayerContext | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"query_result": query_result.model_dump(mode="json")}
    if query_result.proof_map is not None:
        payload["proof_map"] = query_result.proof_map.model_dump(mode="json")
    if taxpayer_ctx is not None:
        payload["taxpayer_context"] = taxpayer_ctx.model_dump(mode="json")
    return payload


def _compose_from_citations(query_result: QueryResponse, limit: int = 3) -> str:
    """Readable prose fallback when plain-language synthesis is unavailable."""
    parts: list[str] = []
    for idx, c in enumerate(query_result.citations[:limit], start=1):
        excerpt = (getattr(c, "text", "") or "").strip()
        if not excerpt:
            continue
        if len(excerpt) > 600:
            excerpt = excerpt[:597].rstrip() + "…"
        label = (
            getattr(c, "section_label", None)
            or getattr(c, "source_doc_id", None)
            or getattr(c, "chunk_id", None)
            or f"Match {idx}"
        )
        parts.append(f"{label}: {excerpt}")
    if not parts:
        return ""
    return (
        "A plain-language summary could not be generated for this turn, so here are the "
        "most relevant passages from the Sri Lankan income-tax sources:\n\n"
        + "\n\n".join(parts)
    )


def _resolve_assistant_text(query_result: QueryResponse) -> str:
    text = query_result.plain_answer
    if not text and query_result.citations:
        text = _compose_from_citations(query_result)
        if text:
            # Surface it through the normal plain-answer channel so the UI and
            # persisted history render prose rather than a raw citation dump.
            query_result.plain_answer = text
    if not text and query_result.domain_message:
        text = query_result.domain_message
    return text or "I could not find grounded legal sources for that question."


@router.post("", response_model=ChatResponse)
async def chat_turn(request: Request, body: ChatRequest) -> ChatResponse:
    settings = get_lm_settings()
    mem_store = getattr(request.app.state, "chat_session_store", None)
    hist_store = getattr(request.app.state, "chat_history_store", None)

    persist = bool(
        settings.COMP_LLM_CHAT_HISTORY_ENABLED and body.user_id and hist_store is not None
    )

    # ------------------------------------------------------------------
    # Resolve / create the session and gather prior user turns.
    # ------------------------------------------------------------------
    if persist:
        session_id = body.session_id
        if session_id and hist_store.get_session_detail(session_id, body.user_id) is None:
            session_id = None  # unknown id or not owned by this user → start fresh
        if not session_id:
            session_id = hist_store.create_session(body.user_id)
            if session_id is None:
                raise HTTPException(status_code=400, detail="Invalid user_id")
        prior_user_turns = hist_store.recent_turns_text(session_id, body.user_id)
        hist_store.append_message(session_id, body.user_id, "user", body.message)
        contextual = _contextual_from_turns(prior_user_turns, body.message)
    else:
        if mem_store is None:
            raise HTTPException(status_code=503, detail="Chat session store unavailable")
        session = mem_store.get(body.session_id) if body.session_id else None
        if session is None:
            session = mem_store.create()
        session_id = session.session_id
        mem_store.append(session_id, "user", body.message)
        contextual = _contextual_question(session.messages, body.message)

    # ------------------------------------------------------------------
    # Taxpayer-specific path (own DB record + IRD citations + KG).
    # ------------------------------------------------------------------
    taxpayer_ctx: TaxpayerContext | None = None
    if settings.COMP_LLM_TAXPAYER_DATA_ENABLED and (
        body.profile_id or looks_taxpayer_specific(body.message)
    ):
        tp = await answer_taxpayer_turn(
            request,
            settings,
            message=body.message,
            retrieval_question=contextual,
            profile_id=body.profile_id,
            top_k=body.top_k,
            assessment_year_hint=body.assessment_year_hint,
        )
        if tp.handled:
            taxpayer_ctx = tp.context
            query_result = tp.query_result or QueryResponse(
                question=body.message,
                normalized_question=body.message,
                top_k=body.top_k or settings.COMP_LLM_RETRIEVAL_TOP_K,
                citations=[],
                retrieval_model="taxpayer-path",
                validation_status="not_run",
            )
            if tp.proof_map is not None:
                query_result.proof_map = tp.proof_map
            assistant_text = tp.answer_text or _resolve_assistant_text(query_result)
            return _finalize(
                persist, hist_store, mem_store, session_id, body,
                query_result, assistant_text, taxpayer_ctx,
            )

    # ------------------------------------------------------------------
    # Standard law-grounded path.
    # ------------------------------------------------------------------
    pipeline = await run_query_pipeline(
        request,
        settings,
        question=body.message,
        retrieval_question=contextual,
        top_k=body.top_k,
        synthesize_answer=body.synthesize_answer,
        assessment_year_hint=body.assessment_year_hint,
        include_proof_map=True,
    )
    query_result = pipeline.response
    if pipeline.proof_map is not None:
        query_result.proof_map = pipeline.proof_map
    assistant_text = _resolve_assistant_text(query_result)
    return _finalize(
        persist, hist_store, mem_store, session_id, body,
        query_result, assistant_text, taxpayer_ctx,
    )


def _finalize(
    persist: bool,
    hist_store: Any,
    mem_store: Any,
    session_id: str,
    body: ChatRequest,
    query_result: QueryResponse,
    assistant_text: str,
    taxpayer_ctx: TaxpayerContext | None,
) -> ChatResponse:
    if persist:
        hist_store.append_message(
            session_id,
            body.user_id,
            "assistant",
            assistant_text,
            payload=_assistant_payload(query_result, taxpayer_ctx),
        )
        detail = hist_store.get_session_detail(session_id, body.user_id)
        history_len = len(detail.messages) if detail else 0
    else:
        mem_store.append(session_id, "assistant", assistant_text)
        updated = mem_store.get(session_id)
        history_len = len(updated.messages) if updated else 0

    return ChatResponse(
        session_id=session_id,
        turn_index=history_len // 2,
        user_message=body.message,
        assistant_message=assistant_text,
        query_result=query_result,
        proof_map=query_result.proof_map,
        history_length=history_len,
        taxpayer_context=taxpayer_ctx,
        persisted=persist,
    )


# ---------------------------------------------------------------------------
# Session history endpoints (per-user)
# ---------------------------------------------------------------------------
def _require_hist_store(request: Request) -> Any:
    store = getattr(request.app.state, "chat_history_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Chat history is not enabled")
    return store


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    request: Request,
    user_id: str = Query(..., description="Caller's users.id (UUID)."),
    include_archived: bool = Query(False),
    limit: int | None = Query(None, ge=1, le=500),
) -> ChatSessionListResponse:
    store = _require_hist_store(request)
    cap = limit or get_lm_settings().COMP_LLM_CHAT_HISTORY_MAX_SESSIONS
    rows = store.list_sessions(user_id, limit=cap, include_archived=include_archived)
    return ChatSessionListResponse(
        user_id=user_id,
        sessions=[
            ChatSessionSummary(
                session_id=r.session_id,
                title=r.title,
                archived=r.archived,
                created_at=r.created_at,
                last_message_at=r.last_message_at,
                message_count=r.message_count,
            )
            for r in rows
        ],
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    request: Request,
    session_id: str,
    user_id: str = Query(..., description="Caller's users.id (UUID); must own the session."),
) -> ChatSessionDetailResponse:
    store = _require_hist_store(request)
    detail = store.get_session_detail(session_id, user_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages: list[ChatHistoryMessage] = []
    for m in detail.messages:
        payload = m.payload or {}
        qr = payload.get("query_result")
        pm = payload.get("proof_map")
        tc = payload.get("taxpayer_context")
        messages.append(
            ChatHistoryMessage(
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                query_result=QueryResponse.model_validate(qr) if qr else None,
                proof_map=ProofMap.model_validate(pm) if pm else None,
                taxpayer_context=TaxpayerContext.model_validate(tc) if tc else None,
            )
        )
    return ChatSessionDetailResponse(
        session_id=detail.session_id,
        title=detail.title,
        archived=detail.archived,
        created_at=detail.created_at,
        last_message_at=detail.last_message_at,
        messages=messages,
    )


@router.patch("/sessions/{session_id}")
async def patch_session(
    request: Request, session_id: str, body: ChatSessionPatchRequest
) -> dict[str, str]:
    store = _require_hist_store(request)
    changed = False
    if body.title is not None:
        changed |= store.rename_session(session_id, body.user_id, body.title)
    if body.archived is not None:
        changed |= store.set_archived(session_id, body.user_id, body.archived)
    if not changed:
        raise HTTPException(status_code=404, detail="Session not found or nothing to change")
    return {"status": "updated", "session_id": session_id}


@router.delete("/sessions/{session_id}")
async def clear_chat_session(
    request: Request,
    session_id: str,
    user_id: str | None = Query(None, description="Caller's users.id; required for persisted sessions."),
) -> dict[str, str]:
    # Persisted per-user session.
    hist_store = getattr(request.app.state, "chat_history_store", None)
    if user_id and hist_store is not None:
        if not hist_store.delete_session(session_id, user_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "session_id": session_id}

    # In-memory demo session.
    mem_store = getattr(request.app.state, "chat_session_store", None)
    if mem_store is None:
        raise HTTPException(status_code=503, detail="Chat session store unavailable")
    if mem_store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    mem_store.delete(session_id)
    return {"status": "deleted", "session_id": session_id}


_GENERIC_FOLLOWUPS = [
    "Who is required to file an income tax return in Sri Lanka?",
    "What are the current personal income tax rates and bands?",
    "What reliefs and deductions can an individual taxpayer claim?",
    "What are the penalties for late filing or late payment?",
    "How is the year of assessment defined for income tax?",
]


def _clean_suggestion(line: str) -> str:
    """Strip list markers / numbering / quotes the model sometimes adds."""
    text = line.strip().lstrip("-*•").strip()
    # drop leading "1." / "1)" / "Q1:" style prefixes
    while text[:1].isdigit():
        text = text[1:]
        text = text.lstrip(".):- ").strip()
    return text.strip().strip('"').strip()


@router.post("/suggestions", response_model=SuggestResponse)
async def suggest_questions(body: SuggestRequest) -> SuggestResponse:
    """Generate 3 follow-up questions based on the last Q&A using Gemini.

    Always returns 3 questions: falls back to generic Sri Lankan income-tax
    follow-ups whenever the model is unavailable or returns nothing usable.
    """
    settings = get_lm_settings()
    fallback = SuggestResponse(suggestions=_GENERIC_FOLLOWUPS[:3])

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
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000,
            # Reasoning "flash" models otherwise burn the whole budget on hidden
            # thinking tokens and return nothing.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                _GEMINI_URL.format(model=settings.COMP_LLM_GEMINI_LIGHT_MODEL),
                params={"key": settings.COMP_LLM_GEMINI_API_KEY},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "\n".join(
            p["text"] for p in parts if isinstance(p, dict) and p.get("text")
        ).strip()
        questions = [
            q for q in (_clean_suggestion(line) for line in text.splitlines()) if len(q) > 8
        ][:3]
    except Exception:
        questions = []

    if len(questions) < 3:
        for extra in _GENERIC_FOLLOWUPS:
            if extra not in questions:
                questions.append(extra)
            if len(questions) == 3:
                break
    return SuggestResponse(suggestions=questions[:3])
