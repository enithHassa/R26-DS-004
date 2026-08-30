"""Optional plain-language answers from retrieved citations + graph context."""

from __future__ import annotations

import httpx

from app.config import LanguageModelSettings
from app.schemas.graph_v1 import GraphContext
from app.schemas.query_v1 import Citation
from backend.shared.utils.logging import logger

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _label(citation: Citation) -> str:
    if citation.section_label and citation.section_label.strip():
        return citation.section_label.strip()
    if citation.source_doc_id and citation.source_doc_id.strip():
        return citation.source_doc_id.strip()
    return citation.chunk_id


def _graph_context_text(context: GraphContext | None) -> str:
    if context is None:
        return "No knowledge-graph context was attached."

    lines: list[str] = []
    if context.concepts:
        lines.append("Concepts:")
        for concept in context.concepts[:8]:
            name = concept.canonical_name or concept.concept_id
            note = f" — {concept.notes}" if concept.notes else ""
            lines.append(f"- {name}{note}")
    if context.reliefs:
        lines.append("Reliefs:")
        for relief in context.reliefs[:8]:
            name = relief.display_name or relief.relief_id
            lines.append(f"- {name}")
    if context.rate_bands:
        lines.append("Rate bands:")
        for band in context.rate_bands[:6]:
            label = band.band_label or band.rate_band_id
            rate = f"{band.rate_percent}%" if band.rate_percent is not None else "unknown rate"
            lines.append(f"- {label}: {rate}")
    if context.procedure_milestones:
        lines.append("Deadlines:")
        for milestone in context.procedure_milestones[:6]:
            lines.append(f"- {milestone.display_name or milestone.milestone_id}")
    if context.taxpayer_profiles:
        lines.append("Taxpayer profiles:")
        for profile in context.taxpayer_profiles[:6]:
            lines.append(f"- {profile.display_name or profile.profile_type}")
    if context.lex_notes:
        lines.append("Override notices:")
        for note in context.lex_notes[:4]:
            lines.append(
                f"- {note.winner_section_uid} overrides {note.overridden_section_uid}"
            )
    if context.superseded_by:
        lines.append("Superseded instruments:")
        for item in context.superseded_by[:6]:
            lines.append(f"- {item}")

    return "\n".join(lines) if lines else "Knowledge graph returned no linked entities."


def build_synthesis_prompt(
    question: str,
    citations: list[Citation],
    graph_context: GraphContext | None,
    *,
    max_citations: int,
    max_chars_per_citation: int,
) -> str:
    blocks: list[str] = [
        "You explain Sri Lankan income tax in plain English for a non-expert reader.",
        "If the question is not about Sri Lankan income tax, reply with exactly:",
        "I can only answer Sri Lankan income-tax questions using the supplied legal sources.",
        "Use only the supplied passages and knowledge-graph notes.",
        "Do not invent statutes, amounts, or deadlines.",
        "Write 2 short paragraphs: first a direct answer, then a short 'What the sources show' section.",
        "Cite passages as [Match 1], [Match 2], etc.",
        "If the evidence is weak or incomplete, say what is missing.",
        "",
        f"Question: {question.strip()}",
        "",
        "Knowledge graph context:",
        _graph_context_text(graph_context),
        "",
        "Retrieved passages:",
    ]

    for index, citation in enumerate(citations[:max_citations], start=1):
        text = (citation.text or "").strip()
        if len(text) > max_chars_per_citation:
            text = text[: max_chars_per_citation - 3] + "..."
        blocks.extend(
            [
                f"[Match {index}] {_label(citation)}",
                text or "(No excerpt text available for this match.)",
                "",
            ]
        )

    return "\n".join(blocks).strip()


async def synthesize_plain_answer(
    settings: LanguageModelSettings,
    question: str,
    citations: list[Citation],
    graph_context: GraphContext | None,
) -> tuple[str | None, str | None, str | None]:
    """Return (answer text, provider id, model id)."""
    if not settings.COMP_LLM_ANSWER_SYNTHESIS_ENABLED:
        return None, None, None
    if settings.COMP_LLM_ANSWER_PROVIDER != "gemini":
        return None, None, None
    if not settings.COMP_LLM_GEMINI_API_KEY:
        return None, None, None
    if not citations:
        return None, None, None

    prompt = build_synthesis_prompt(
        question,
        citations,
        graph_context,
        max_citations=settings.COMP_LLM_ANSWER_MAX_CITATIONS,
        max_chars_per_citation=settings.COMP_LLM_ANSWER_MAX_CHARS_PER_CITATION,
    )
    model = settings.COMP_LLM_GEMINI_MODEL
    url = _GEMINI_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": settings.COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.COMP_LLM_ANSWER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                params={"key": settings.COMP_LLM_GEMINI_API_KEY},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "\n".join(
            part["text"].strip()
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ).strip()
        if not text:
            return None, "gemini", model
        return text, "gemini", model
    except Exception as exc:
        logger.warning("Answer synthesis failed: {}", exc)
        return None, "gemini", model
