"""Optional plain-language answers from retrieved citations + graph context."""

from __future__ import annotations

import httpx

from app.config import LanguageModelSettings
from app.schemas.graph_v1 import GraphContext
from app.schemas.query_v1 import Citation
from app.services.ird_reference_facts import reference_notes_for
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
    reference_notes: str | None = None,
) -> str:
    blocks: list[str] = [
        "You explain Sri Lankan income tax in plain English for a non-expert reader.",
        "If the question is not about Sri Lankan income tax, reply with exactly:",
        "I can only answer Sri Lankan income-tax questions using the supplied legal sources.",
        "Use only the supplied passages, knowledge-graph notes, and IRD reference notes.",
        "Do not invent statutes, amounts, or deadlines that are absent from all of those.",
        "When an IRD reference note gives a specific date, amount, or statutory section, "
        "state it directly in your answer and attribute it to the Inland Revenue Act "
        "section it names.",
        "Write 2 short paragraphs: first a direct answer, then a short 'What the sources show' section.",
        "Always lead with the most complete direct answer the sources support — including any "
        "specific rate, amount, date, or deadline that the passages or knowledge-graph notes do "
        "state. Only after giving that answer, note any part that the sources leave unspecified. "
        "Do not open the reply with what is missing.",
        "Cite passages as [Match 1], [Match 2], etc.",
        "",
        f"Question: {question.strip()}",
        "",
        "Knowledge graph context:",
        _graph_context_text(graph_context),
        "",
        "IRD reference notes (well-established procedural facts; use when relevant):",
        reference_notes or "None supplied.",
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
        reference_notes=reference_notes_for(question),
    )
    model = settings.COMP_LLM_GEMINI_MODEL
    url = _GEMINI_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": settings.COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS,
            # Gemini 2.5 / 3.x "flash" are reasoning models: without this they
            # spend the whole maxOutputTokens budget on hidden thinking tokens
            # and return an empty answer with finishReason=MAX_TOKENS.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(
                timeout=settings.COMP_LLM_ANSWER_TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    url,
                    params={"key": settings.COMP_LLM_GEMINI_API_KEY},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            candidate = (data.get("candidates") or [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            text = "\n".join(
                part["text"].strip()
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ).strip()
            if text:
                return text, "gemini", model
            finish = candidate.get("finishReason")
            feedback = data.get("promptFeedback")
            if finish == "MAX_TOKENS":
                logger.warning(
                    "Answer synthesis hit MAX_TOKENS with no text (model={}, "
                    "maxOutputTokens={}). Raise COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS "
                    "or use a non-reasoning model.",
                    model,
                    settings.COMP_LLM_ANSWER_MAX_OUTPUT_TOKENS,
                )
            else:
                logger.warning(
                    "Answer synthesis returned no text (attempt {}/2); "
                    "finishReason={} promptFeedback={}",
                    attempt + 1,
                    finish,
                    feedback,
                )
        except httpx.TimeoutException as exc:
            # A timeout already consumed the full request budget; retrying would
            # only double the latency the caller waits on. Give up now.
            logger.warning("Answer synthesis timed out (attempt {}/2): {}", attempt + 1, exc)
            return None, "gemini", model
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = (exc.response.text or "")[:500]
            if status == 429:
                logger.warning(
                    "Answer synthesis quota / rate limit exceeded (HTTP 429, model={}). "
                    "Body: {}",
                    model,
                    body,
                )
                return None, "gemini", model  # retrying a 429 immediately won't help
            if status in (401, 403):
                logger.warning(
                    "Answer synthesis auth failed (HTTP {}, model={}). The Gemini API "
                    "key may be invalid or expired. Body: {}",
                    status,
                    model,
                    body,
                )
                return None, "gemini", model
            if status == 400:
                logger.warning(
                    "Answer synthesis bad request (HTTP 400, model={}). Check the model "
                    "name is valid. Body: {}",
                    model,
                    body,
                )
                return None, "gemini", model
            last_exc = exc
            logger.warning(
                "Answer synthesis HTTP {} (attempt {}/2). Body: {}", status, attempt + 1, body
            )
        except Exception as exc:  # noqa: BLE001 - transient upstream failures
            last_exc = exc
            logger.warning("Answer synthesis failed (attempt {}/2): {}", attempt + 1, exc)

    if last_exc is not None:
        logger.warning("Answer synthesis gave up after retry: {}", last_exc)
    return None, "gemini", model
