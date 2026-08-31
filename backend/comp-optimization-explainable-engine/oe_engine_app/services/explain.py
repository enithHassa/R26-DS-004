"""Explain = calc trace + retrieve (Phase 2 chunks). No live GPT in Phase 4."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from oe_engine_app.services import calculate as calc_engine
from oe_engine_app.services.retrieve import hits_to_json, hybrid_retrieve

DISCLAIMER = "Research prototype — not legal advice."


def _as_int(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _trace_query(calc: dict[str, Any]) -> str:
    parts: list[str] = []
    for line in calc.get("relief_lines") or []:
        if _as_int(line.get("applied")) > 0:
            parts.append(str(line.get("display_name") or line.get("compare_group_id") or ""))
            quote = str(line.get("quote") or "").strip()
            if quote:
                parts.append(quote[:180])
    for line in calc.get("slab_lines") or []:
        if _as_int(line.get("tax")) > 0:
            parts.append(str(line.get("band_label") or "rate band"))
            quote = str(line.get("quote") or "").strip()
            if quote:
                parts.append(quote[:180])
    return " ".join(p for p in parts if p).strip() or "income tax relief rate"


def explain(
    session: Session,
    assessment_year: str,
    income: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    exclude_source_doc_id: str | None = None,
    wht_already_paid: int = 0,
    apit_already_paid: int = 0,
    *,
    query_embedding: list[float] | None = None,
) -> dict[str, Any]:
    calc = calc_engine.calculate(
        session,
        assessment_year=assessment_year,
        income=income,
        claims=claims,
        exclude_source_doc_id=exclude_source_doc_id,
        wht_already_paid=wht_already_paid,
        apit_already_paid=apit_already_paid,
    )
    query = _trace_query(calc)
    hits = hybrid_retrieve(
        session,
        query=query,
        query_embedding=query_embedding,
        top_k=6,
    )
    return {
        **calc,
        "disclaimer": DISCLAIMER,
        "mode": "trace_retrieve",
        "status": "ok",
        "retrieve_query": query,
        "hits": hits_to_json(hits),
        "hit_count": len(hits),
    }
