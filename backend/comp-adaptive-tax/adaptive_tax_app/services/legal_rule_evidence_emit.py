"""Build non-executable LegalRuleEvidence candidates from RAG evidence chunks.

Phase 11c — optional emission on the explain :class:`EvidenceBundle`.
Caps / formulas stay null until human validation (and still non-executable).
"""

from __future__ import annotations

import re
from adaptive_tax_app.schemas.evidence import EvidenceBundle, EvidenceChunk
from adaptive_tax_app.schemas.extracted_rule import AssessmentYearLiteral
from adaptive_tax_app.schemas.legal_rule_evidence import LegalRuleEvidence

_RE_SECTION_NUM = re.compile(r"(?i)\bsection\s+(\d+[a-z]?)\b")
_RE_FIRST_SCHED = re.compile(r"(?i)\bfirst\s+schedule\b")


def _section_label_from_chunk(chunk: EvidenceChunk) -> str | None:
    ref = chunk.section_ref
    if isinstance(ref, str) and ref.strip():
        if _RE_FIRST_SCHED.search(ref):
            return "First Schedule"
        m = _RE_SECTION_NUM.search(ref)
        if m:
            return m.group(1)
        # Already bare / short
        bare = ref.strip()
        if bare.lower().startswith("section "):
            return bare.split(None, 1)[-1]
        return bare
    text = chunk.text or ""
    if _RE_FIRST_SCHED.search(text[:120]):
        return "First Schedule"
    m = _RE_SECTION_NUM.search(text[:200])
    if m:
        return m.group(1)
    return None


def _quote_from_chunk(chunk: EvidenceChunk, *, min_len: int = 20) -> str | None:
    text = " ".join((chunk.text or "").split())
    if len(text) < min_len:
        return None
    # Keep a bounded verbatim window for the evidence object
    return text[:800]


def candidate_from_operative_chunk(
    chunk: EvidenceChunk,
    *,
    assessment_year: AssessmentYearLiteral | str | None = None,
) -> LegalRuleEvidence | None:
    """Emit a ``candidate`` evidence object for one operative Act chunk.

    Numeric / formula fields are intentionally null (not invented).
    """
    if chunk.is_header_footer:
        return None
    if chunk.is_toc and not chunk.is_operative_provision:
        return None
    # Prefer operative; allow unknown operative flag when not TOC
    if chunk.is_operative_provision is False and chunk.is_toc:
        return None

    section = _section_label_from_chunk(chunk)
    if not section:
        return None
    quote = _quote_from_chunk(chunk)
    if not quote:
        return None

    ya: AssessmentYearLiteral | None = None
    if assessment_year in ("2024_25", "2025_26"):
        ya = assessment_year  # type: ignore[assignment]

    # parent_provision_id is not on EvidenceChunk — leave null unless present later
    return LegalRuleEvidence(
        section=section,
        paragraph=chunk.paragraph_ref,
        paragraph_ref=chunk.paragraph_ref,
        assessment_year=ya,
        rule_type=None,
        condition=None,
        formula=None,
        cap_value=None,
        threshold=None,
        maximum=None,
        allowed=None,
        applicability_note=(
            "Phase 11c candidate from operative RAG chunk — "
            "not calculation; caps/formula null until validated."
        ),
        effective_date=None,
        source_doc_id=chunk.source_doc_id,
        source_chunk_ids=[chunk.chunk_id] if chunk.chunk_id else [],
        parent_provision_id=None,
        source_quote=quote,
        status="candidate",
        executable=False,
    )


def build_candidate_legal_rule_evidence(
    bundle: EvidenceBundle,
    *,
    assessment_year: AssessmentYearLiteral | str | None = None,
    max_items: int = 12,
) -> list[LegalRuleEvidence]:
    """Attach-ready candidates from operative (or non-TOC) chunks in ``bundle``."""
    out: list[LegalRuleEvidence] = []
    seen_chunks: set[str] = set()

    # Prefer chunks cited by step-local evidence when available
    preferred_ids: list[str] = []
    for st in bundle.step_evidence or []:
        preferred_ids.extend(st.evidence_chunk_ids or [])
    preferred = set(preferred_ids)

    ordered: list[EvidenceChunk] = []
    by_id = {c.chunk_id: c for c in bundle.chunks if c.chunk_id}
    for cid in preferred_ids:
        ch = by_id.get(cid)
        if ch is not None and cid not in seen_chunks:
            ordered.append(ch)
            seen_chunks.add(cid)
    for ch in bundle.chunks:
        if ch.chunk_id in seen_chunks:
            continue
        if ch.is_operative_provision is True or (
            not ch.is_toc and not ch.is_header_footer
        ):
            ordered.append(ch)
            if ch.chunk_id:
                seen_chunks.add(ch.chunk_id)

    for ch in ordered:
        if len(out) >= max_items:
            break
        # Skip clear TOC-only
        if ch.is_toc and ch.is_operative_provision is not True:
            continue
        cand = candidate_from_operative_chunk(ch, assessment_year=assessment_year)
        if cand is not None:
            out.append(cand)
    return out


def attach_legal_rule_evidence_candidates(
    bundle: EvidenceBundle,
    *,
    assessment_year: AssessmentYearLiteral | str | None = None,
) -> EvidenceBundle:
    """Return a copy of ``bundle`` with ``legal_rule_evidence`` candidates filled."""
    candidates = build_candidate_legal_rule_evidence(
        bundle, assessment_year=assessment_year
    )
    return bundle.model_copy(update={"legal_rule_evidence": candidates})
