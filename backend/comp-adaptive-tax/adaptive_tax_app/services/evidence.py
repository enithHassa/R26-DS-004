"""Gather RAG + Postgres + Neo4j evidence for Phase 4 explanations.

Flow:
1. Collect unique ``section_uids`` from a calculation trace.
2. Map each uid → human section label (e.g. ``...::sec::section_52`` → ``Section 52``).
3. Retrieve Chroma chunks per label (digit-aware section_ref matching).
4. Optionally load approved ``rule_source`` quotes intersecting cited sections.
5. Optionally enrich with Neo4j ``MODIFIES`` edges.
6. Section-matched bootstrap quotes from the calc response (tier 4 fallback).
7. Per-step local evidence gate (Phase 7b).

If both ``chunks`` and ``source_quotes`` are empty, callers must set
``insufficient_evidence=true`` and must not call GPT.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxResponseV1,
    CalculationTraceStep,
    RuleSourceRef,
)
from adaptive_tax_app.schemas.evidence import (
    EvidenceBundle,
    EvidenceChunk,
    EvidenceSourceQuote,
    GraphModifiesEdge,
    StepEvidenceStatus,
)

# Trailing ontology slug → display label used for RAG + faithfulness.
_SLUG_LABELS: dict[str, str] = {
    "section_5": "Section 5",
    "section_52": "Section 52",
    "first_schedule": "First Schedule",
}

STEP_EVIDENCE_UNAVAILABLE = "Evidence unavailable for this step"

_RE_PARAGRAPH_CITE = re.compile(
    r"(?i)\b(?:sec(?:tion)?\.?\s*)?(\d+[a-z]?)\s*\(\s*(\d+[a-z]?)\s*\)"
)

_MODIFIES_CYPHER = """
MATCH (a:LawInstrument)-[r:MODIFIES]->(s:Section)
WHERE s.section_uid IN $section_uids
RETURN a.source_doc_id AS amendment_source_doc_id,
       s.section_uid AS section_uid,
       s.section_label AS section_label,
       r.source_note AS source_note,
       r.effective_from AS effective_from
ORDER BY s.section_uid, a.source_doc_id
"""


def section_uid_slug(section_uid: str) -> str:
    """Return the ``::sec::`` slug, or the last path segment."""
    text = (section_uid or "").strip()
    if "::sec::" in text:
        return text.rsplit("::sec::", 1)[-1].strip().lower()
    if "::" in text:
        return text.rsplit("::", 1)[-1].strip().lower()
    return text.lower()


def section_uid_to_label(section_uid: str) -> str | None:
    """Map ontology ``section_uid`` → normalized display label for citations."""
    slug = section_uid_slug(section_uid)
    if not slug:
        return None
    if slug in _SLUG_LABELS:
        return _SLUG_LABELS[slug]

    m = re.fullmatch(r"section[_\s-]*(\d+[a-z]?)", slug, flags=re.I)
    if m:
        return f"Section {m.group(1)}"

    words = [w for w in re.split(r"[_\s-]+", slug) if w]
    if not words:
        return None
    titled = " ".join(w.capitalize() for w in words)
    if words[0].lower() == "section" and len(words) >= 2:
        return f"Section {words[1]}"
    return titled


def section_label_tokens(label: str) -> list[str]:
    """Tokens useful for matching Postgres ``section`` / ``amends_section``."""
    label = (label or "").strip()
    if not label:
        return []
    tokens = [label]
    m = re.search(r"(\d+[a-z]?)", label, flags=re.I)
    if m:
        tokens.append(m.group(1))
    bare = re.sub(r"^section\s+", "", label, flags=re.I).strip()
    if bare and bare not in tokens:
        tokens.append(bare)
    return list(dict.fromkeys(tokens))


def section_ref_matches(haystack: str | None, label: str) -> bool:
    """True when a Chroma ``section_ref`` refers to ``label`` (digit-aware).

    Prevents ``Section 5`` from matching ``Section 52``.
    """
    if not haystack or not label:
        return False
    h = str(haystack).lower()
    lab = label.strip().lower()

    num_m = re.search(r"section\s+(\d+[a-z]?)", lab)
    if not num_m:
        return lab in h or lab.replace(" ", "") in h.replace(" ", "")

    num = num_m.group(1).lower()
    if re.search(rf"section\s*{re.escape(num)}(?!\d)", h):
        return True
    if re.search(rf"(?:^|[^0-9a-z]){re.escape(num)}(?![0-9a-z])", h):
        if "section" in h or num == lab or lab.endswith(num):
            return True
    return False


def infer_paragraph_ref(
    step: CalculationTraceStep | None = None,
    *,
    description: str | None = None,
    step_id: str | None = None,
) -> str | None:
    """Extract paragraph cite like ``52(4)`` from a calc step description/id."""
    text = description
    sid = step_id
    if step is not None:
        text = step.description
        sid = step.step_id
    blob = f"{text or ''} {sid or ''}"
    m = _RE_PARAGRAPH_CITE.search(blob)
    if m:
        return f"{m.group(1)}({m.group(2)})"
    return None


def build_step_aware_query(
    *,
    label: str,
    step: CalculationTraceStep | None = None,
    paragraph_ref: str | None = None,
) -> str:
    """Semantic query: description + concepts + section/paragraph labels."""
    parts: list[str] = [label]
    if paragraph_ref:
        parts.append(f"paragraph {paragraph_ref}")
        parts.append(paragraph_ref)
    if step is not None:
        if (step.description or "").strip():
            parts.append(step.description.strip())
        for cid in step.concept_ids or []:
            if cid and str(cid).strip():
                parts.append(str(cid).replace("_", " "))
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return " ".join(out)


def collect_section_uids(
    response: CalculateTaxResponseV1 | None = None,
    *,
    trace: Sequence[CalculationTraceStep] | None = None,
    extra_section_uids: Sequence[str] | None = None,
) -> list[str]:
    """Deduped section_uids from a calculate response / trace (trace order first)."""
    uids: list[str] = []
    steps = list(trace or [])
    if response is not None:
        steps = list(response.calculation_trace)
    for step in steps:
        uids.extend(step.section_uids)
    if response is not None:
        for ref in response.rule_source_refs:
            if ref.section_uid:
                uids.append(ref.section_uid)
    if extra_section_uids:
        uids.extend(extra_section_uids)
    return list(dict.fromkeys(u for u in uids if u and str(u).strip()))


def labels_for_section_uids(section_uids: Sequence[str]) -> list[str]:
    """Map uids → unique normalized labels (order-preserving)."""
    labels: list[str] = []
    for uid in section_uids:
        label = section_uid_to_label(uid)
        if label and label not in labels:
            labels.append(label)
    return labels


def _chunk_usable_for_step(chunk: EvidenceChunk) -> bool:
    """TOC / header-footer alone must not unlock a step narrative."""
    if chunk.is_header_footer:
        return False
    if chunk.is_toc and not chunk.is_operative_provision:
        return False
    return True


def _paragraph_ok_for_step(
    chunk: EvidenceChunk,
    paragraph_ref: str | None,
) -> bool:
    if not paragraph_ref:
        return True
    from adaptive_tax_app.services.legal_authority import _paragraph_matches

    return _paragraph_matches(chunk.paragraph_ref, paragraph_ref, chunk.text or "")


def _pg_section_intersects(rule_section: str | None, tokens: set[str]) -> bool:
    raw = (rule_section or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    for tok in tokens:
        t = tok.lower()
        if lowered == t:
            return True
        if t.isdigit() or re.fullmatch(r"\d+[a-z]?", t):
            if re.search(rf"(?:^|[^0-9a-z]){re.escape(t)}(?![0-9a-z])", lowered):
                return True
        elif t in lowered:
            return True
    return False


def local_evidence_for_step(
    step: CalculationTraceStep,
    bundle: EvidenceBundle,
    *,
    paragraph_ref: str | None = None,
) -> tuple[list[str], str | None]:
    """Return step-local chunk ids + quote id (never unrelated global hits)."""
    labels = labels_for_section_uids(step.section_uids)
    para = paragraph_ref or infer_paragraph_ref(step)

    if not labels:
        return [], None

    def _matches_label(chunk: EvidenceChunk, lab: str) -> bool:
        # Prefer structured section_ref — bare string mention in unrelated
        # sections must not unlock the step (citation/support correctness).
        if chunk.section_ref:
            return bool(section_ref_matches(chunk.section_ref, lab))
        return bool(section_ref_matches(chunk.text[:400], lab))

    chunk_ids: list[str] = []
    for chunk in bundle.chunks:
        if not _chunk_usable_for_step(chunk):
            continue
        if para and not _paragraph_ok_for_step(chunk, para):
            continue
        for lab in labels:
            if _matches_label(chunk, lab):
                if chunk.chunk_id not in chunk_ids:
                    chunk_ids.append(chunk.chunk_id)
                break

    if para and not chunk_ids:
        for chunk in bundle.chunks:
            if not _chunk_usable_for_step(chunk):
                continue
            for lab in labels:
                if _matches_label(chunk, lab):
                    if chunk.chunk_id not in chunk_ids:
                        chunk_ids.append(chunk.chunk_id)
                    break

    rule_id: str | None = None
    for quote in bundle.source_quotes:
        blob = f"{quote.section} {quote.amends_section or ''}"
        for lab in labels:
            toks = set(section_label_tokens(lab))
            if _pg_section_intersects(quote.section, toks) or _pg_section_intersects(
                quote.amends_section, toks
            ):
                rule_id = quote.rule_source_id
                break
            if section_ref_matches(blob, lab):
                rule_id = quote.rule_source_id
                break
        if rule_id:
            break

    return chunk_ids, rule_id


def build_step_evidence_statuses(
    steps: Sequence[CalculationTraceStep],
    bundle: EvidenceBundle,
) -> list[StepEvidenceStatus]:
    """Phase 7b: gate each step on step-local Act-backed evidence."""
    out: list[StepEvidenceStatus] = []
    for step in steps:
        labels = labels_for_section_uids(step.section_uids)
        para = infer_paragraph_ref(step)
        if not labels:
            out.append(
                StepEvidenceStatus(
                    step_id=step.step_id,
                    evidence_available=True,
                    section_labels=[],
                    paragraph_ref=para,
                    evidence_chunk_ids=[],
                    rule_source_id=None,
                    reason="no_section_anchor",
                )
            )
            continue
        chunk_ids, rule_id = local_evidence_for_step(step, bundle, paragraph_ref=para)
        available = bool(chunk_ids or rule_id)
        out.append(
            StepEvidenceStatus(
                step_id=step.step_id,
                evidence_available=available,
                section_labels=labels,
                paragraph_ref=para,
                evidence_chunk_ids=chunk_ids,
                rule_source_id=rule_id,
                reason=None if available else "no_step_local_act_evidence",
            )
        )
    return out


def _chroma_chunks_for_label(
    label: str,
    *,
    index: Any,
    top_k: int,
    assessment_year: str | None = None,
    paragraph_ref: str | None = None,
    min_score: float | None = None,
    query: str | None = None,
) -> list[EvidenceChunk]:
    """Search Chroma for ``label``; filter + rank by legal precedence then score."""
    from adaptive_tax_app.services.legal_authority import (
        legal_precedence_tier,
        sort_hits_by_legal_precedence,
    )

    n_fetch = max(top_k * 8, 24)
    search_q = (query or label).strip() or label
    try:
        hits = index.search(search_q, section_ref=None, top_k=n_fetch)
    except Exception:  # noqa: BLE001
        return []

    section_hits: list[Any] = []
    for hit in hits:
        meta = hit.metadata if isinstance(getattr(hit, "metadata", None), dict) else {}
        if meta.get("is_header_footer") in (True, "true", "1", 1):
            continue
        if not section_ref_matches(hit.section_ref, label):
            if hit.section_ref:
                continue
            if not section_ref_matches(hit.text[:500], label):
                continue
        section_hits.append(hit)

    ranked = sort_hits_by_legal_precedence(
        section_hits,
        assessment_year=assessment_year,
        section_label=label,
        paragraph_ref=paragraph_ref,
        section_ref_matches_fn=section_ref_matches,
        min_score=min_score,
    )

    out: list[EvidenceChunk] = []
    seen: set[str] = set()
    for hit in ranked:
        if hit.chunk_id in seen:
            continue
        seen.add(hit.chunk_id)
        meta = hit.metadata if isinstance(getattr(hit, "metadata", None), dict) else {}
        para = meta.get("paragraph_ref")
        inst = meta.get("instrument_type")

        def _b(key: str) -> bool | None:
            if key not in meta:
                return None
            val = meta.get(key)
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            if s in {"1", "true", "yes", "y"}:
                return True
            if s in {"0", "false", "no", "n", ""}:
                return False
            return None

        matched = bool(section_ref_matches(hit.section_ref, label)) or bool(
            section_ref_matches(hit.text[:500], label)
        )
        tier = legal_precedence_tier(
            source_doc_id=hit.source_doc_id,
            instrument_type=str(inst) if inst else None,
            assessment_year=assessment_year,
            section_matched=matched,
            paragraph_ref_wanted=paragraph_ref,
            paragraph_ref_chunk=str(para) if para else None,
            text=hit.text or "",
        )
        out.append(
            EvidenceChunk(
                chunk_id=hit.chunk_id,
                text=hit.text,
                section_ref=hit.section_ref,
                source_doc_id=hit.source_doc_id,
                page=hit.page,
                score=hit.score,
                paragraph_ref=str(para) if para else None,
                instrument_type=str(inst) if inst else None,
                legal_precedence_tier=tier,
                is_operative_provision=_b("is_operative_provision"),
                is_toc=_b("is_toc"),
                is_header_footer=_b("is_header_footer"),
                is_cross_reference=_b("is_cross_reference"),
            )
        )
        if len(out) >= top_k:
            break
    return out


_EXPLAIN_BLOCKED_SOURCE_DOC_IDS = frozenset(
    {
        "ird-calc-ontology-v5",
        "ird-guide-ira",
    }
)


def filter_explain_chunks(chunks: Sequence[EvidenceChunk]) -> list[EvidenceChunk]:
    """Drop non-authoritative sources from explain retrieval (Master PDF, etc.)."""
    return [
        c
        for c in chunks
        if (c.source_doc_id or "").strip() not in _EXPLAIN_BLOCKED_SOURCE_DOC_IDS
    ]


def _fetch_source_quotes(
    db: Session,
    *,
    labels: Sequence[str],
) -> list[EvidenceSourceQuote]:
    from adaptive_tax_app.db_loader import RuleSource, RuleSourceStatus

    tokens: set[str] = set()
    for label in labels:
        tokens.update(section_label_tokens(label))
    if not tokens:
        return []

    stmt = select(RuleSource).where(RuleSource.status == RuleSourceStatus.APPROVED)
    rows = list(db.scalars(stmt).all())

    out: list[EvidenceSourceQuote] = []
    for row in rows:
        if not (
            _pg_section_intersects(row.section, tokens)
            or _pg_section_intersects(row.amends_section, tokens)
        ):
            continue
        status_val = row.status.value if row.status is not None else ""
        out.append(
            EvidenceSourceQuote(
                rule_source_id=str(row.id),
                section=row.section,
                amends_section=row.amends_section,
                source_quote=row.source_quote,
                concept_id=row.concept_id,
                maximum=row.maximum,
                status=status_val,
                amendment_job_id=str(row.amendment_job_id) if row.amendment_job_id else None,
            )
        )
    return out


def _bootstrap_quotes_from_calc(
    refs: Sequence[RuleSourceRef],
    *,
    labels: Sequence[str],
    already: Sequence[EvidenceSourceQuote],
) -> list[EvidenceSourceQuote]:
    """Section-matched bootstrap quotes (precedence tier 4) — never wrong-section."""
    if not refs or not labels:
        return []
    have_ids = {q.rule_source_id for q in already}
    out: list[EvidenceSourceQuote] = []
    for ref in refs:
        quote = (ref.source_quote or "").strip()
        if not quote:
            continue
        sid = (ref.id or "").strip()
        if not sid or sid in have_ids:
            continue
        if (ref.source_doc_id or "").strip() in _EXPLAIN_BLOCKED_SOURCE_DOC_IDS:
            continue
        matched_labels: list[str] = []
        for lab in labels:
            toks = set(section_label_tokens(lab))
            if _pg_section_intersects(ref.section, toks):
                matched_labels.append(lab)
                continue
            if ref.section_uid:
                uid_lab = section_uid_to_label(ref.section_uid)
                if uid_lab == lab:
                    matched_labels.append(lab)
        if not matched_labels:
            continue
        status = (ref.status or "").strip().lower() or "bootstrap"
        if sid.startswith("bootstrap:") or status not in {"approved", "bootstrap"}:
            status = "bootstrap"
        out.append(
            EvidenceSourceQuote(
                rule_source_id=sid,
                section=ref.section or matched_labels[0],
                amends_section=None,
                source_quote=quote,
                concept_id=ref.concept_id,
                maximum=None,
                status=status,
                amendment_job_id=None,
            )
        )
        have_ids.add(sid)
    return out


def _fetch_modifies_edges(section_uids: Sequence[str]) -> list[GraphModifiesEdge]:
    if not section_uids:
        return []
    try:
        from adaptive_tax_app.services.kg_client import open_neo4j_driver

        driver = open_neo4j_driver()
    except Exception:  # noqa: BLE001
        return []

    try:
        with driver.session() as session:
            rows = session.run(
                _MODIFIES_CYPHER,
                section_uids=list(section_uids),
            ).data()
    except Exception:  # noqa: BLE001
        return []
    finally:
        try:
            driver.close()
        except Exception:  # noqa: BLE001
            pass

    out: list[GraphModifiesEdge] = []
    for row in rows:
        doc_id = row.get("amendment_source_doc_id")
        uid = row.get("section_uid")
        if not doc_id or not uid:
            continue
        eff = row.get("effective_from")
        out.append(
            GraphModifiesEdge(
                amendment_source_doc_id=str(doc_id),
                section_uid=str(uid),
                section_label=str(row["section_label"]) if row.get("section_label") else None,
                source_note=str(row["source_note"]) if row.get("source_note") else None,
                effective_from=str(eff) if eff is not None else None,
            )
        )
    return out


def _label_query_context(
    steps: Sequence[CalculationTraceStep],
    labels: Sequence[str],
    *,
    global_paragraph_ref: str | None,
) -> dict[str, tuple[CalculationTraceStep | None, str | None]]:
    """Pick the most specific step context per section label."""
    ctx: dict[str, tuple[CalculationTraceStep | None, str | None]] = {
        lab: (None, global_paragraph_ref) for lab in labels
    }
    for step in steps:
        para = infer_paragraph_ref(step) or global_paragraph_ref
        for uid in step.section_uids:
            lab = section_uid_to_label(uid)
            if not lab or lab not in ctx:
                continue
            prev_step, prev_para = ctx[lab]
            if prev_step is None or (para and not prev_para):
                ctx[lab] = (step, para)
    return ctx


def gather_evidence(
    response: CalculateTaxResponseV1 | None = None,
    *,
    trace: Sequence[CalculationTraceStep] | None = None,
    extra_section_uids: Sequence[str] | None = None,
    db: Session | None = None,
    chroma_index: Any | None = None,
    top_k_per_section: int = 3,
    include_graph_modifies: bool = True,
    assessment_year: str | None = None,
    paragraph_ref: str | None = None,
    min_score: float | None = None,
) -> EvidenceBundle:
    """Build an :class:`EvidenceBundle` for the given calculation trace.

    Chroma hits are ranked by **legal-document precedence** for ``assessment_year``
    before raw similarity. ``min_score`` is a retrieval noise floor only — never
    legal confidence.
    """
    from adaptive_tax_app.config import get_adaptive_tax_settings
    from adaptive_tax_app.services.legal_authority import (
        assessment_year_from_trace_inputs,
        normalize_assessment_year,
    )

    warnings: list[str] = []
    section_uids = collect_section_uids(
        response, trace=trace, extra_section_uids=extra_section_uids
    )
    labels = labels_for_section_uids(section_uids)

    steps = list(trace or [])
    if response is not None and not steps:
        steps = list(response.calculation_trace)
    ya = normalize_assessment_year(assessment_year) or assessment_year_from_trace_inputs(
        steps
    )
    score_floor = min_score
    if score_floor is None:
        try:
            score_floor = float(get_adaptive_tax_settings().RAG_MIN_SCORE)
        except Exception:  # noqa: BLE001
            score_floor = 0.55

    # Bootstrap may only satisfy sections cited by the calc trace (not by refs alone).
    trace_labels = labels_for_section_uids(
        [uid for step in steps for uid in step.section_uids]
    )

    label_ctx = _label_query_context(steps, labels, global_paragraph_ref=paragraph_ref)

    chunks: list[EvidenceChunk] = []
    sections_with_chunks: set[str] = set()
    seen_chunk_ids: set[str] = set()

    if labels:
        index = chroma_index
        if index is None:
            try:
                from adaptive_tax_app.services.chroma_index import get_chroma_index

                index = get_chroma_index()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"chroma_unavailable: {exc}")
                index = None

        if index is not None:
            for label in labels:
                step_ctx, para = label_ctx.get(label, (None, paragraph_ref))
                query = build_step_aware_query(
                    label=label, step=step_ctx, paragraph_ref=para
                )
                try:
                    found = _chroma_chunks_for_label(
                        label,
                        index=index,
                        top_k=top_k_per_section,
                        assessment_year=ya,
                        paragraph_ref=para,
                        min_score=score_floor,
                        query=query,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"chroma_search_failed:{label}:{exc}")
                    continue
                kept_for_label = 0
                for ch in found:
                    if (ch.source_doc_id or "").strip() in _EXPLAIN_BLOCKED_SOURCE_DOC_IDS:
                        continue
                    if ch.chunk_id in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(ch.chunk_id)
                    chunks.append(ch)
                    kept_for_label += 1
                if kept_for_label:
                    sections_with_chunks.add(label)

    source_quotes: list[EvidenceSourceQuote] = []
    sections_with_quotes: set[str] = set()
    if db is not None and labels:
        try:
            source_quotes = _fetch_source_quotes(db, labels=labels)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"rule_source_query_failed: {exc}")
            source_quotes = []
        for q in source_quotes:
            for label in labels:
                toks = set(section_label_tokens(label))
                if _pg_section_intersects(q.section, toks) or _pg_section_intersects(
                    q.amends_section, toks
                ):
                    sections_with_quotes.add(label)

    if response is not None and trace_labels:
        boot = _bootstrap_quotes_from_calc(
            response.rule_source_refs, labels=trace_labels, already=source_quotes
        )
        source_quotes.extend(boot)
        for q in boot:
            for label in labels:
                toks = set(section_label_tokens(label))
                if _pg_section_intersects(q.section, toks):
                    sections_with_quotes.add(label)

    graph_modifies: list[GraphModifiesEdge] = []
    if include_graph_modifies and section_uids:
        try:
            graph_modifies = _fetch_modifies_edges(section_uids)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"neo4j_modifies_failed: {exc}")
            graph_modifies = []

    sections_retrieved = [
        lab for lab in labels if lab in sections_with_chunks or lab in sections_with_quotes
    ]

    bundle = EvidenceBundle(
        chunks=chunks,
        source_quotes=source_quotes,
        sections_retrieved=sections_retrieved,
        sections_queried=labels,
        graph_modifies=graph_modifies,
        warnings=warnings,
    )
    bundle.step_evidence = build_step_evidence_statuses(steps, bundle)
    # Phase 11c — optional non-executable structured evidence candidates
    try:
        from adaptive_tax_app.services.legal_rule_evidence_emit import (
            build_candidate_legal_rule_evidence,
        )

        bundle.legal_rule_evidence = build_candidate_legal_rule_evidence(
            bundle, assessment_year=ya
        )
    except Exception as exc:  # noqa: BLE001 — never break explain for candidates
        bundle.warnings = list(bundle.warnings) + [
            f"legal_rule_evidence_emit_failed: {exc}"
        ]
    return bundle


def gather_field_evidence(
    *,
    section_uid: str | None,
    rule_source_id: str | None = None,
    db: Session | None = None,
    chroma_index: Any | None = None,
    top_k: int = 3,
) -> EvidenceBundle:
    """Chroma + optional Postgres quotes for one catalog field (Phase 6.6)."""
    warnings: list[str] = []
    section_uids = [section_uid] if section_uid else []
    labels = labels_for_section_uids(section_uids)

    chunks: list[EvidenceChunk] = []
    if labels:
        index = chroma_index
        if index is None:
            try:
                from adaptive_tax_app.services.chroma_index import get_chroma_index

                index = get_chroma_index()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"chroma_unavailable: {exc}")
                index = None
        if index is not None:
            for label in labels:
                try:
                    found = filter_explain_chunks(
                        _chroma_chunks_for_label(label, index=index, top_k=top_k)
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"chroma_search_failed:{label}:{exc}")
                    continue
                chunks.extend(found)

    source_quotes: list[EvidenceSourceQuote] = []
    if db is not None and labels:
        try:
            source_quotes = _fetch_source_quotes(db, labels=labels)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"rule_source_query_failed: {exc}")
            source_quotes = []

    if rule_source_id and source_quotes:
        rid = rule_source_id.strip()
        narrowed = [q for q in source_quotes if q.rule_source_id == rid]
        if narrowed:
            source_quotes = narrowed

    sections_with_chunks = {lab for lab in labels if any(chunks)}
    sections_with_quotes = set()
    for q in source_quotes:
        for label in labels:
            toks = set(section_label_tokens(label))
            if _pg_section_intersects(q.section, toks) or _pg_section_intersects(
                q.amends_section, toks
            ):
                sections_with_quotes.add(label)

    sections_retrieved = [
        lab for lab in labels if lab in sections_with_chunks or lab in sections_with_quotes
    ]

    return EvidenceBundle(
        chunks=chunks,
        source_quotes=source_quotes,
        sections_retrieved=sections_retrieved,
        sections_queried=labels,
        graph_modifies=[],
        warnings=warnings,
    )


def passes_rag_min_score(score: float | None, min_score: float | None) -> bool:
    """True when ``score`` clears the retrieval noise floor (NOT legal confidence)."""
    if min_score is None:
        return True
    if score is None:
        return True
    return float(score) >= float(min_score)


def has_insufficient_evidence(bundle: EvidenceBundle) -> bool:
    """Caller helper: skip GPT when True."""
    return bundle.insufficient_evidence
