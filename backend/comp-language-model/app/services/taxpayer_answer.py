"""Taxpayer-grounded chat answers.

Pipeline for a taxpayer-specific turn:

1. Resolve + load the caller's taxpayer record from the shared DB.
2. Run the normal law-grounded query pipeline (IRD citations + knowledge graph).
3. Ask Gemini to synthesise an answer from DB facts + citations + KG context,
   allowed to note where more information would be needed (gap-fill), but not
   to invent figures.
4. Think Twice symbolic validation on the draft.
5. Cross-check the draft against the knowledge-graph context and record a
   consistency verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Request

from app.config import LanguageModelSettings
from app.schemas.chat_v1 import TaxpayerContext
from app.schemas.graph_v1 import GraphContext
from app.schemas.query_v1 import QueryResponse
from app.services.answer_synthesis import _graph_context_text, _label
from app.services.query_pipeline import run_query_pipeline
from app.services.taxpayer_data import (
    TaxpayerFacts,
    extract_name_hint,
    format_taxpayer_block,
    load_taxpayer_facts,
    resolve_taxpayer,
)
from app.services.taxpayer_intent import select_context_sources
from app.services.think_twice import apply_think_twice
from backend.shared.utils.logging import logger

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass(slots=True)
class TaxpayerAnswer:
    handled: bool
    answer_text: str | None
    query_result: QueryResponse | None
    proof_map: object | None
    context: TaxpayerContext


async def _call_gemini(settings: LanguageModelSettings, prompt: str, max_tokens: int) -> str | None:
    if not settings.COMP_LLM_GEMINI_API_KEY:
        return None
    model = settings.COMP_LLM_GEMINI_MODEL
    # Keep reasoning models from spending the whole token budget on hidden
    # thinking (empty answer, finishReason=MAX_TOKENS). Gemini 3.x rejects
    # thinkingBudget and uses thinkingLevel instead.
    thinking_config = (
        {"thinkingLevel": "low"} if model.startswith("gemini-3") else {"thinkingBudget": 0}
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": thinking_config,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.COMP_LLM_ANSWER_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                _GEMINI_URL.format(model=settings.COMP_LLM_GEMINI_MODEL),
                params={"key": settings.COMP_LLM_GEMINI_API_KEY},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "\n".join(
            p["text"].strip() for p in parts if isinstance(p, dict) and p.get("text")
        ).strip()
        return text or None
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("taxpayer_answer Gemini call failed: {}", exc)
        return None


def _citation_block(query_result: QueryResponse, max_citations: int, max_chars: int) -> str:
    blocks: list[str] = []
    for i, c in enumerate(query_result.citations[:max_citations], start=1):
        t = (c.text or "").strip()
        if len(t) > max_chars:
            t = t[: max_chars - 3] + "..."
        blocks.append(f"[Match {i}] {_label(c)}\n{t or '(no excerpt)'}")
    return "\n\n".join(blocks) if blocks else "(no IRD passages retrieved)"


def _build_prompt(
    question: str,
    facts: TaxpayerFacts,
    query_result: QueryResponse,
    graph_context: GraphContext | None,
    *,
    max_citations: int,
    max_chars: int,
) -> str:
    return "\n".join(
        [
            "You are a Sri Lankan income-tax advisor answering about ONE specific taxpayer.",
            "You are given: (a) that taxpayer's record and related system context from the ",
            "tax-advisory database — which may include classified transactions (with the ",
            "reasoning behind each classification), personalized recommendations and their ",
            "rationale, behavioural/risk answers, financial history, filed return detail, and ",
            "active adaptive-tax rule amendments; (b) relevant passages from the Inland ",
            "Revenue Act / IRD rules; and (c) knowledge-graph context (rate bands, reliefs, overrides).",
            "",
            "Rules:",
            "- Use the taxpayer record for every taxpayer-specific number. Never invent figures.",
            "- Apply the law from the passages and the KG rate bands/reliefs to those numbers.",
            "- When the question is about a transaction, a recommendation, or a config change, "
            "explain the recorded reasoning for it — do not just restate the label or amount.",
            "- If a figure needed for an accurate answer is not in the context, say exactly what is missing.",
            "- Show the calculation steps when you compute tax, assessable income, or a relief.",
            "- Cite legal passages as [Match 1], [Match 2].",
            "- Formatting: plain Markdown for a chat UI — short paragraphs, '-' bullets, "
            "'1.' numbering for calculation steps, bold only for key terms. Do NOT use "
            "LaTeX or $ / $$ math delimiters; write formulas inline in plain text, e.g. "
            "'min(cap 1,800,000, income 3,800,000) = 1,800,000'.",
            "- End with a one-line 'Confidence:' note (high / medium / low) and why.",
            "",
            f"QUESTION: {question.strip()}",
            "",
            format_taxpayer_block(facts),
            "",
            "KNOWLEDGE-GRAPH CONTEXT:",
            _graph_context_text(graph_context),
            "",
            "IRD PASSAGES:",
            _citation_block(query_result, max_citations, max_chars),
        ]
    )


async def _kg_consistency(
    settings: LanguageModelSettings, answer_text: str, graph_context: GraphContext | None
) -> str:
    if graph_context is None:
        return "not_checked (no knowledge-graph context available)"
    prompt = "\n".join(
        [
            "Check whether the ANSWER is consistent with the KNOWLEDGE GRAPH context below.",
            "Focus on tax rates, rate bands, relief amounts, thresholds and any override notices.",
            "Reply with one line: 'consistent', 'inconsistent: <reason>', or 'unverifiable: <reason>'.",
            "",
            "ANSWER:",
            answer_text,
            "",
            "KNOWLEDGE GRAPH:",
            _graph_context_text(graph_context),
        ]
    )
    verdict = await _call_gemini(settings, prompt, max_tokens=300)
    return (verdict or "not_checked").splitlines()[0].strip()


async def answer_taxpayer_turn(
    request: Request,
    settings: LanguageModelSettings,
    *,
    message: str,
    retrieval_question: str,
    profile_id: str | None,
    top_k: int | None,
    assessment_year_hint: str | None,
) -> TaxpayerAnswer:
    ctx = TaxpayerContext(used=False, profile_id=profile_id)

    name_hint = extract_name_hint(message)
    resolution = resolve_taxpayer(caller_profile_id=profile_id, name_hint=name_hint)
    if resolution.status != "ok":
        ctx.note = resolution.message
        return TaxpayerAnswer(
            handled=True,
            answer_text=resolution.message,
            query_result=None,
            proof_map=None,
            context=ctx,
        )

    sources = select_context_sources(
        message,
        routing_enabled=settings.COMP_LLM_TAXPAYER_CONTEXT_INTENT_ROUTING,
    )
    facts = load_taxpayer_facts(
        resolution.profile_id,  # type: ignore[arg-type]
        monthly_lookback=settings.COMP_LLM_TAXPAYER_MONTHLY_LOOKBACK,
        sources=sources,
        max_transactions=settings.COMP_LLM_TAXPAYER_MAX_TRANSACTIONS,
        max_recommendations=settings.COMP_LLM_TAXPAYER_MAX_RECOMMENDATIONS,
        history_lookback=settings.COMP_LLM_TAXPAYER_HISTORY_LOOKBACK,
    )
    if facts is None:
        ctx.note = "Your taxpayer profile exists but has no readable detail rows yet."
        return TaxpayerAnswer(
            handled=True,
            answer_text=ctx.note,
            query_result=None,
            proof_map=None,
            context=ctx,
        )

    pipeline = await run_query_pipeline(
        request,
        settings,
        question=message,
        retrieval_question=retrieval_question,
        top_k=top_k,
        synthesize_answer=False,  # we do our own taxpayer-aware synthesis below
        assessment_year_hint=assessment_year_hint,
        include_proof_map=True,
    )
    query_result = pipeline.response
    graph_context = query_result.graph_context

    prompt = _build_prompt(
        message,
        facts,
        query_result,
        graph_context,
        max_citations=settings.COMP_LLM_ANSWER_MAX_CITATIONS,
        max_chars=settings.COMP_LLM_ANSWER_MAX_CHARS_PER_CITATION,
    )
    draft = await _call_gemini(settings, prompt, settings.COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS)

    if not draft:
        ctx.used = True
        ctx.profile_id = facts.profile_id
        ctx.taxpayer_name = facts.full_name
        ctx.tax_year = facts.tax_year
        ctx.fields_used = facts.fields_used
        ctx.context_sources = facts.sources_requested
        ctx.note = "Answer synthesis was unavailable; returning retrieved legal passages only."
        return TaxpayerAnswer(
            handled=True,
            answer_text=(
                "I have your taxpayer record and the relevant law, but the answer "
                "generator is unavailable right now. See the cited passages in the payload."
            ),
            query_result=query_result,
            proof_map=pipeline.proof_map,
            context=ctx,
        )

    think = apply_think_twice(settings, draft, assessment_year_hint=assessment_year_hint)
    final_text = think.answer_text or draft
    kg_verdict = await _kg_consistency(settings, final_text, graph_context)

    query_result.plain_answer = final_text
    query_result.answer_provider = "gemini"
    query_result.answer_model = settings.COMP_LLM_GEMINI_MODEL
    query_result.validation_status = think.validation_status

    ctx.used = True
    ctx.profile_id = facts.profile_id
    ctx.taxpayer_name = facts.full_name
    ctx.tax_year = facts.tax_year
    ctx.fields_used = facts.fields_used
    ctx.context_sources = facts.sources_requested
    ctx.kg_consistency = kg_verdict
    if think.validation_status == "corrected":
        ctx.note = "Draft answer failed symbolic validation and was replaced with a safe fallback."

    return TaxpayerAnswer(
        handled=True,
        answer_text=final_text,
        query_result=query_result,
        proof_map=pipeline.proof_map,
        context=ctx,
    )
