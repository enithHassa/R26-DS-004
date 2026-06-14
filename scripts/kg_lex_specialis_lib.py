"""Phase 3 Step 8 — Lex Specialis metadata derived from corpus norm rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_LEX_PATH = _REPO / "knowledge_graph" / "lex_specialis_v1.json"


def load_lex_spec(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_LEX_PATH
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def infer_authority_class(norm: dict[str, Any]) -> str:
    """Infer authority_class from manifest-style fields on a normalized chunk row."""
    is_draft = bool(norm.get("is_draft", False))
    it = (norm.get("instrument_type") or "").lower()
    dt = (norm.get("doc_type") or "").lower()
    tier = (norm.get("tier") or "").upper()

    if is_draft and any(x in it or x in dt for x in ("guide", "draft")):
        return "draft_guide"
    if "consolidated" in it or "consolidated" in dt:
        return "consolidated"
    if "amendment" in it or "amendment" in dt:
        return "amendment"
    if "circular" in it or "circular" in dt:
        return "circular"
    if any(x in it or x in dt for x in ("ruling", "interpretation")):
        return "ruling"
    if "guide" in it or "guide" in dt:
        return "guide"
    if tier == "A":
        return "statute"
    if tier == "B":
        return "guide"
    if tier == "C":
        return "hub_summary"
    return "other"


def _parse_weight(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lex_fields_for(
    norm: dict[str, Any],
    *,
    role: str,
    lex_path: Path | None = None,
) -> dict[str, Any]:
    """Return Lex Specialis properties for Neo4j. role: LawInstrument | Section | TextChunk."""
    spec = load_lex_spec(lex_path)
    classes: dict[str, Any] = spec.get("classes") or {}
    ac = infer_authority_class(norm)
    if ac not in classes:
        ac = "other"

    base_rank = int(classes[ac]["base_specificity_rank"])
    bonus = int(spec.get("section_specificity_bonus", 5))
    if role == "Section":
        specificity_rank = base_rank + bonus
    else:
        specificity_rank = base_rank

    w = _parse_weight(norm.get("authority_weight"))
    if w is None:
        w = float(classes[ac]["default_weight"])
    w = max(0.0, min(1.0, w))

    ef = (norm.get("effective_from") or norm.get("effective_start_date") or "").strip()
    et = (norm.get("effective_end_date") or "").strip()

    out: dict[str, Any] = {
        "authority_class": ac,
        "authority_weight_numeric": w,
        "specificity_rank": specificity_rank,
        "lex_effective_from": ef if ef else None,
        "lex_effective_to": et if et else None,
    }
    return out


def authority_precedence_index(authority_class: str, lex_path: Path | None = None) -> int:
    """Lower index = weaker authority in ties (see lex_specialis_v1 precedence_order)."""
    order = load_lex_spec(lex_path).get("precedence_order") or []
    try:
        return int(order.index(authority_class))
    except ValueError:
        return len(order) // 2
