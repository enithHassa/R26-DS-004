"""Live OpenAI narrative after calculate. Engine amounts stay the source of truth."""

from __future__ import annotations

import json
import logging
from typing import Any

from opt_explain_app.config import OptimizationExplainableSettings, get_oe_settings
from opt_explain_app.services import calculate as calc_engine
from opt_explain_app.services import rag_index

logger = logging.getLogger(__name__)

DISCLAIMER = "Research prototype — not legal advice."

_SYSTEM_PROMPT = """You explain a Sri Lankan income-tax result to someone with NO tax background.

Audience: a first-time user who does not know acts, schedules, or tax jargon.

Writing style:
- Plain English, short sentences, friendly tone.
- Prefer everyday words: "money you earned", "amount taken off", "what is left to tax",
  "tax you pay" — not "gross income", "taxable income", or "provision" unless you
  immediately explain them in brackets.
- Mention only reliefs and rate bands that appear in the trace with applied/tax > 0.
- Do NOT list reliefs that were not used (applied is 0).
- Keep the whole narrative under 120 words.

Structure (use blank lines between paragraphs):
1. One sentence: total income and year of assessment.
2. One short paragraph: each relief actually used, with its amount in Rs.
3. One sentence: income left to tax and final tax payable (engine numbers only).
4. Optional one sentence: name the main act/schedule that backs the biggest relief — only
   if it appears in the supplied quotes.

Rules:
1. Use only the calculation trace and quoted provisions supplied by the user.
2. Do not invent, change, or introduce any amounts, rates, caps, or tax figures.
3. Do not invent legal sections or act names. Cite only act_name and section_ref
   from the supplied quotes.
4. If a quote is missing for a line, do not guess the legal text.
5. Return JSON only: {"narrative": string, "cited_sections": string[]}.
6. cited_sections must be copied from the supplied section_ref values used in the narrative.
"""


class ExplainError(RuntimeError):
    """OpenAI or configuration failure for POST /explain."""


def _as_int(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def collect_quotes(calc: dict[str, Any]) -> list[dict[str, str]]:
    """Quotes for reliefs/slabs that actually affected this scenario."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    relief_lines = [
        line
        for line in (calc.get("relief_lines") or [])
        if _as_int(line.get("applied")) > 0
    ]
    slab_lines = [
        line
        for line in (calc.get("slab_lines") or [])
        if _as_int(line.get("tax")) > 0 or _as_int(line.get("slice")) > 0
    ]
    for line in relief_lines + slab_lines:
        quote = str(line.get("quote") or "").strip()
        if not quote:
            continue
        key = (
            str(line.get("source_doc_id") or ""),
            str(line.get("section_ref") or ""),
            quote[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "entry_id": str(line.get("entry_id") or ""),
                "display_name": str(line.get("display_name") or line.get("band_label") or ""),
                "act_name": str(line.get("act_name") or ""),
                "section_ref": str(line.get("section_ref") or ""),
                "source_doc_id": str(line.get("source_doc_id") or ""),
                "quote": quote,
            }
        )
    return out


def missing_quote_lines(calc: dict[str, Any]) -> list[str]:
    """Applied reliefs and used slabs must carry a RAG quote."""
    missing: list[str] = []
    for line in calc.get("relief_lines") or []:
        if _as_int(line.get("applied")) <= 0:
            continue
        if not str(line.get("quote") or "").strip():
            missing.append(str(line.get("display_name") or line.get("entry_id") or "relief"))
    for line in calc.get("slab_lines") or []:
        if _as_int(line.get("tax")) <= 0 and _as_int(line.get("slice")) <= 0:
            continue
        if not str(line.get("quote") or "").strip():
            missing.append(str(line.get("band_label") or f"band {line.get('band_index')}"))
    return missing


def _chat_kwargs(model: str) -> dict[str, Any]:
    name = (model or "").strip().lower()
    if name.startswith("gpt-5"):
        return {}
    return {"temperature": 0}


def build_user_prompt(calc: dict[str, Any], quotes: list[dict[str, str]]) -> str:
    trace = {
        "assessment_year": calc.get("assessment_year"),
        "exclude_source_doc_id": calc.get("exclude_source_doc_id"),
        "gross_income": calc.get("gross_income"),
        "total_reliefs": calc.get("total_reliefs"),
        "taxable_income": calc.get("taxable_income"),
        "tax_payable": calc.get("tax_payable"),
        "relief_lines": [
            {
                "display_name": line.get("display_name"),
                "applied": line.get("applied"),
                "cap": line.get("cap"),
                "formula": line.get("formula"),
                "act_name": line.get("act_name"),
                "section_ref": line.get("section_ref"),
                "source_doc_id": line.get("source_doc_id"),
            }
            for line in (calc.get("relief_lines") or [])
            if _as_int(line.get("applied")) > 0
        ],
        "slab_lines": [
            {
                "band_label": line.get("band_label"),
                "rate_percent": line.get("rate_percent"),
                "slice": line.get("slice"),
                "tax": line.get("tax"),
                "act_name": line.get("act_name"),
                "section_ref": line.get("section_ref"),
                "source_doc_id": line.get("source_doc_id"),
            }
            for line in (calc.get("slab_lines") or [])
            if _as_int(line.get("tax")) > 0 or _as_int(line.get("slice")) > 0
        ],
    }
    return (
        "Calculation trace (engine source of truth — do not change these numbers):\n"
        f"{json.dumps(trace, indent=2, ensure_ascii=False)}\n\n"
        "Retrieved quotes (cite only these acts/sections):\n"
        f"{json.dumps(quotes, indent=2, ensure_ascii=False)}\n"
    )


def _complete_openai(user_prompt: str, settings: OptimizationExplainableSettings) -> dict[str, Any]:
    if not (settings.OPENAI_API_KEY or "").strip():
        raise ExplainError(
            "Live explain needs OPENAI_API_KEY (COMP_OPTIMIZATION_EXPLAINABLE_EXPLAIN_MODE=openai)."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ExplainError("openai package is not installed") from exc

    model = settings.COMP_OPTIMIZATION_EXPLAINABLE_OPENAI_EXPLAIN_MODEL
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            **_chat_kwargs(model),
        )
    except Exception as exc:  # noqa: BLE001
        raise ExplainError(f"OpenAI explanation failed: {exc}") from exc

    content = (completion.choices[0].message.content or "").strip()
    if not content:
        raise ExplainError("OpenAI returned an empty explanation")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExplainError("OpenAI explanation was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ExplainError("OpenAI explanation JSON must be an object")
    return parsed


def _engine_block(calc: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessment_year": calc.get("assessment_year"),
        "gross_income": calc.get("gross_income"),
        "total_reliefs": calc.get("total_reliefs"),
        "taxable_income": calc.get("taxable_income"),
        "tax_payable": calc.get("tax_payable"),
        "exclude_source_doc_id": calc.get("exclude_source_doc_id"),
    }


def explain_from_calculation(
    calc: dict[str, Any],
    *,
    settings: OptimizationExplainableSettings | None = None,
) -> dict[str, Any]:
    cfg = settings or get_oe_settings()
    quotes = collect_quotes(calc)
    missing = missing_quote_lines(calc)
    base = {
        **_engine_block(calc),
        "disclaimer": DISCLAIMER,
        "model": cfg.COMP_OPTIMIZATION_EXPLAINABLE_OPENAI_EXPLAIN_MODEL,
        "mode": "openai",
        "citations": quotes,
        "narrative": "",
        "cited_sections": [],
    }
    if missing or not quotes:
        logger.info("Explain insufficient_evidence (missing=%s)", missing)
        return {
            **base,
            "insufficient_evidence": True,
            "status": "insufficient_evidence",
            "detail": "Missing quotes for: " + ", ".join(missing) if missing else "No RAG quotes on this trace.",
        }

    parsed = _complete_openai(build_user_prompt(calc, quotes), cfg)
    narrative = str(parsed.get("narrative") or "").strip()
    cited = parsed.get("cited_sections")
    if not isinstance(cited, list):
        cited = []
    allowed = {str(q.get("section_ref") or "").strip() for q in quotes}
    cited_clean = [str(item).strip() for item in cited if str(item).strip() in allowed]
    if not narrative:
        return {
            **base,
            "insufficient_evidence": True,
            "status": "insufficient_evidence",
            "detail": "The model returned no narrative.",
        }
    return {
        **base,
        "insufficient_evidence": False,
        "status": "ok",
        "narrative": narrative,
        "cited_sections": cited_clean,
        "detail": None,
    }


def explain(
    assessment_year: str,
    income: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    exclude_source_doc_id: str | None = None,
    *,
    settings: OptimizationExplainableSettings | None = None,
) -> dict[str, Any]:
    rag_index.ensure_index()
    calc = calc_engine.calculate(
        assessment_year=assessment_year,
        income=income,
        claims=claims,
        exclude_source_doc_id=exclude_source_doc_id,
    )
    return explain_from_calculation(calc, settings=settings)
