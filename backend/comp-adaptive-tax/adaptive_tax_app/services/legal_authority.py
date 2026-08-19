"""Legal-document authority metadata and RAG ranking precedence.

Precedence (applied **before** raw similarity decides the winner):

1. Exact applicable provision (YA + section + paragraph when cited)
2. Applicable amendment / consolidated for that YA
3. Base Act provision still in force for that YA
4. (Bootstrap quotes are handled outside Chroma ranking)
5. Insufficient / wrong-YA / blocked — ranked last or filtered

Similarity score is only a noise filter / tie-break **within** the same tier.
Never treat Chroma score as legal confidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from backend.shared.config.settings import PROJECT_ROOT

_MANIFEST_PATH = PROJECT_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"

# Lower = better.
TIER_EXACT_PARAGRAPH = 0
TIER_AMENDMENT_OR_CONSOLIDATED = 1
TIER_BASE_ACT = 2
TIER_YA_UNKNOWN = 3
TIER_YA_UNKNOWN_BASE = 4
TIER_BOOTSTRAP = 5  # Section-matched calc bootstrap quotes (fallback only)
TIER_WRONG_YA = 90
TIER_BLOCKED = 99

_BLOCKED = frozenset({"ird-guide-ira", "ird-calc-ontology-v5"})


def normalize_assessment_year(value: str | None) -> str | None:
    """Normalize ``2025/26``, ``2025-26``, ``2025_26`` → ``2025_26``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("/", "_").replace("-", "_")
    m = re.fullmatch(r"(20\d{2})_(\d{2})", text)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    return text


@dataclass(frozen=True)
class DocAuthority:
    source_doc_id: str
    instrument_type: str
    publication_date: str | None
    effective_start_date: str | None
    effective_end_date: str | None
    applicable_assessment_years: tuple[str, ...]
    usable_for_explain: bool


@lru_cache
def load_doc_authority_table(
    manifest_path: str | None = None,
) -> dict[str, DocAuthority]:
    path = Path(manifest_path) if manifest_path else _MANIFEST_PATH
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, DocAuthority] = {}
    for doc in raw.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        sid = str(doc.get("source_doc_id") or "").strip()
        if not sid:
            continue
        yas_raw = doc.get("applicable_assessment_years") or []
        yas: list[str] = []
        if isinstance(yas_raw, list):
            for y in yas_raw:
                ny = normalize_assessment_year(str(y))
                if ny:
                    yas.append(ny)
        usable = doc.get("usable_for_explain")
        if usable is None:
            usable = True
        out[sid] = DocAuthority(
            source_doc_id=sid,
            instrument_type=str(doc.get("instrument_type") or "").strip().lower(),
            publication_date=(str(doc["publication_date"]).strip() or None)
            if doc.get("publication_date")
            else None,
            effective_start_date=(str(doc["effective_start_date"]).strip() or None)
            if doc.get("effective_start_date")
            else None,
            effective_end_date=(str(doc["effective_end_date"]).strip() or None)
            if doc.get("effective_end_date")
            else None,
            applicable_assessment_years=tuple(yas),
            usable_for_explain=bool(usable),
        )
    return out


def doc_ya_status(source_doc_id: str | None, assessment_year: str | None) -> str:
    """Return ``match`` | ``mismatch`` | ``unknown`` | ``blocked`` for ranking."""
    sid = (source_doc_id or "").strip()
    if not sid or sid in _BLOCKED:
        return "blocked"
    ya = normalize_assessment_year(assessment_year)
    table = load_doc_authority_table()
    auth = table.get(sid)
    if auth is None:
        return "unknown"
    if not auth.usable_for_explain:
        return "blocked"
    if not ya or not auth.applicable_assessment_years:
        return "unknown"
    if ya in auth.applicable_assessment_years:
        return "match"
    return "mismatch"


def _paragraph_matches(chunk_paragraph: str | None, wanted: str | None, text: str) -> bool:
    if not wanted:
        return False
    want = wanted.strip().lower().replace(" ", "")
    if chunk_paragraph:
        got = chunk_paragraph.strip().lower().replace(" ", "")
        if got == want:
            return True
        # Allow chunk metadata that is more specific, e.g. want 52(4), got 52(4)(a)
        if got.startswith(want) and len(got) > len(want):
            return True
        # Do NOT treat bare "52" as matching "52(4)"
    # Digit-aware search in text, e.g. 52(4)
    m = re.fullmatch(r"(\d+[a-z]?)\((\d+[a-z]?(?:\(\w+\))*)\)", want, flags=re.I)
    if m:
        sec, para = m.group(1), m.group(2)
        if re.search(
            rf"(?i)\b{re.escape(sec)}\s*\(\s*{re.escape(para)}\s*\)",
            text or "",
        ):
            return True
    return False


def legal_precedence_tier(
    *,
    source_doc_id: str | None,
    instrument_type: str | None = None,
    assessment_year: str | None,
    section_matched: bool,
    paragraph_ref_wanted: str | None = None,
    paragraph_ref_chunk: str | None = None,
    text: str = "",
) -> int:
    """Return sort tier (lower is better)."""
    ya_status = doc_ya_status(source_doc_id, assessment_year)
    if ya_status == "blocked":
        return TIER_BLOCKED
    if not section_matched:
        return TIER_WRONG_YA

    table = load_doc_authority_table()
    auth = table.get((source_doc_id or "").strip())
    inst = (instrument_type or (auth.instrument_type if auth else "") or "").lower()

    para_ok = _paragraph_matches(paragraph_ref_chunk, paragraph_ref_wanted, text)

    if ya_status == "mismatch":
        return TIER_WRONG_YA

    if ya_status == "match" and para_ok and paragraph_ref_wanted:
        return TIER_EXACT_PARAGRAPH

    if ya_status == "match":
        if inst in {"amendment_act", "amendment", "consolidated"}:
            return TIER_AMENDMENT_OR_CONSOLIDATED
        if inst in {"base_act", "base"}:
            return TIER_BASE_ACT
        # Unknown instrument but YA match — treat like amendment tier if not base
        return TIER_AMENDMENT_OR_CONSOLIDATED

    # YA unknown: still prefer amendments slightly over base when both unknown
    if inst in {"amendment_act", "amendment", "consolidated"}:
        return TIER_YA_UNKNOWN
    if inst in {"base_act", "base"}:
        return TIER_YA_UNKNOWN_BASE
    return TIER_YA_UNKNOWN


def _meta_bool(meta: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        val = meta.get(key)
        if isinstance(val, bool):
            return val
        if str(val).strip().lower() in {"1", "true", "yes", "y"}:
            return True
    return False


def rank_key_for_chunk(
    chunk: Any,
    *,
    assessment_year: str | None,
    section_label: str,
    paragraph_ref: str | None = None,
    section_ref_matches_fn: Any,
) -> tuple[int, int, int, float]:
    """Sort key: (tier ↑, toc_penalty ↑, non_operative ↑, -score)."""
    text = getattr(chunk, "text", "") or ""
    section_ref = getattr(chunk, "section_ref", None)
    source_doc_id = getattr(chunk, "source_doc_id", None)
    score = getattr(chunk, "score", None)
    score_f = float(score) if score is not None else 0.0

    meta = getattr(chunk, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    instrument_type = meta.get("instrument_type")
    paragraph_chunk = meta.get("paragraph_ref") or getattr(chunk, "paragraph_ref", None)

    matched = bool(section_ref_matches_fn(section_ref, section_label)) or bool(
        section_ref_matches_fn(text[:500], section_label)
    )
    tier = legal_precedence_tier(
        source_doc_id=source_doc_id,
        instrument_type=str(instrument_type) if instrument_type else None,
        assessment_year=assessment_year,
        section_matched=matched,
        paragraph_ref_wanted=paragraph_ref,
        paragraph_ref_chunk=str(paragraph_chunk) if paragraph_chunk else None,
        text=text,
    )
    is_toc = _meta_bool(meta, "is_toc") or bool(getattr(chunk, "is_toc", False))
    is_hf = _meta_bool(meta, "is_header_footer") or bool(
        getattr(chunk, "is_header_footer", False)
    )
    is_op = _meta_bool(meta, "is_operative_provision") or bool(
        getattr(chunk, "is_operative_provision", False)
    )
    toc_penalty = 1 if (is_toc or is_hf) else 0
    non_operative = 0 if is_op else 1
    return (tier, toc_penalty, non_operative, -score_f)


def sort_hits_by_legal_precedence(
    hits: Sequence[Any],
    *,
    assessment_year: str | None,
    section_label: str,
    paragraph_ref: str | None,
    section_ref_matches_fn: Any,
    min_score: float | None,
) -> list[Any]:
    """Filter by min_score (retrieval noise only), then sort by legal tier then score."""
    filtered: list[Any] = []
    for hit in hits:
        score = getattr(hit, "score", None)
        if min_score is not None and score is not None and float(score) < float(min_score):
            continue
        filtered.append(hit)

    return sorted(
        filtered,
        key=lambda h: rank_key_for_chunk(
            h,
            assessment_year=assessment_year,
            section_label=section_label,
            paragraph_ref=paragraph_ref,
            section_ref_matches_fn=section_ref_matches_fn,
        ),
    )


def assessment_year_from_trace_inputs(trace: Sequence[Any] | None) -> str | None:
    """Best-effort YA from calculation_trace step inputs."""
    if not trace:
        return None
    for step in trace:
        inputs = getattr(step, "inputs", None) or {}
        if isinstance(inputs, dict):
            for key in ("assessment_year", "ya", "year"):
                if key in inputs:
                    return normalize_assessment_year(str(inputs[key]))
    return None
