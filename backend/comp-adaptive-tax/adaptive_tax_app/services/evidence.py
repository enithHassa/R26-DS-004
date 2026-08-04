"""Gather RAG + Postgres + Neo4j evidence for Phase 4 explanations.

Flow:
1. Collect unique ``section_uids`` from a calculation trace.
2. Map each uid → human section label (e.g. ``...::sec::section_52`` → ``Section 52``).
3. Retrieve Chroma chunks per label (digit-aware section_ref matching).
4. Optionally load approved ``rule_source`` quotes intersecting cited sections.
5. Optionally enrich with Neo4j ``MODIFIES`` edges.

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
)
from adaptive_tax_app.schemas.evidence import (
    EvidenceBundle,
    EvidenceChunk,
    EvidenceSourceQuote,
    GraphModifiesEdge,
)

# Trailing ontology slug → display label used for RAG + faithfulness.
_SLUG_LABELS: dict[str, str] = {
    "section_5": "Section 5",
    "section_52": "Section 52",
    "first_schedule": "First Schedule",
}

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

    # section_123 → Section 123
    m = re.fullmatch(r"section[_\s-]*(\d+[a-z]?)", slug, flags=re.I)
    if m:
        return f"Section {m.group(1)}"

    # first_schedule-style snake → Title Case
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
    # Also bare lowercased label without "Section "
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

    # First Schedule / non-numeric labels: substring is enough.
    num_m = re.search(r"section\s+(\d+[a-z]?)", lab)
    if not num_m:
        return lab in h or lab.replace(" ", "") in h.replace(" ", "")

    num = num_m.group(1).lower()
    # "section 5" must not match "section 52"
    if re.search(rf"section\s*{re.escape(num)}(?!\d)", h):
        return True
    # Standalone number token in metadata lists (avoid 5 inside 52)
    if re.search(rf"(?:^|[^0-9a-z]){re.escape(num)}(?![0-9a-z])", h):
        # Prefer when "section" also appears nearby, else accept bare "52"
        if "section" in h or num == lab or lab.endswith(num):
            return True
    return False


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


def _chroma_chunks_for_label(
    label: str,
    *,
    index: Any,
    top_k: int,
) -> list[EvidenceChunk]:
    """Search Chroma for ``label``; filter hits with digit-aware matching."""
    # Do not pass section_ref to Chroma equality/substring filter — "Section 5"
    # is a substring of "Section 52". Filter ourselves after over-fetch.
    n_fetch = max(top_k * 8, 24)
    try:
        hits = index.search(label, section_ref=None, top_k=n_fetch)
    except Exception:  # noqa: BLE001 — empty evidence rather than hard-fail explain
        return []

    out: list[EvidenceChunk] = []
    seen: set[str] = set()
    for hit in hits:
        if not section_ref_matches(hit.section_ref, label):
            # Also accept when query matched but metadata section_ref empty —
            # only if the chunk text mentions the label with digit boundaries.
            if hit.section_ref:
                continue
            if not section_ref_matches(hit.text[:500], label):
                continue
        if hit.chunk_id in seen:
            continue
        seen.add(hit.chunk_id)
        out.append(
            EvidenceChunk(
                chunk_id=hit.chunk_id,
                text=hit.text,
                section_ref=hit.section_ref,
                source_doc_id=hit.source_doc_id,
                page=hit.page,
                score=hit.score,
            )
        )
        if len(out) >= top_k:
            break
    return out


def _pg_section_intersects(rule_section: str | None, tokens: set[str]) -> bool:
    raw = (rule_section or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    for tok in tokens:
        t = tok.lower()
        if lowered == t:
            return True
        # "52" vs "Section 52"
        if t.isdigit() or re.fullmatch(r"\d+[a-z]?", t):
            if re.search(rf"(?:^|[^0-9a-z]){re.escape(t)}(?![0-9a-z])", lowered):
                return True
        elif t in lowered:
            return True
    return False


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


def _fetch_modifies_edges(section_uids: Sequence[str]) -> list[GraphModifiesEdge]:
    if not section_uids:
        return []
    try:
        from adaptive_tax_app.services.kg_client import open_neo4j_driver

        driver = open_neo4j_driver()
    except Exception:  # noqa: BLE001 — Neo4j optional for evidence
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


def gather_evidence(
    response: CalculateTaxResponseV1 | None = None,
    *,
    trace: Sequence[CalculationTraceStep] | None = None,
    extra_section_uids: Sequence[str] | None = None,
    db: Session | None = None,
    chroma_index: Any | None = None,
    top_k_per_section: int = 3,
    include_graph_modifies: bool = True,
) -> EvidenceBundle:
    """Build an :class:`EvidenceBundle` for the given calculation trace.

    Chroma / Neo4j / Postgres failures degrade to empty lists + warnings — they
    do not raise (so explain can return ``insufficient_evidence`` cleanly).
    """
    warnings: list[str] = []
    section_uids = collect_section_uids(
        response, trace=trace, extra_section_uids=extra_section_uids
    )
    labels = labels_for_section_uids(section_uids)

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
                try:
                    found = _chroma_chunks_for_label(
                        label, index=index, top_k=top_k_per_section
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"chroma_search_failed:{label}:{exc}")
                    continue
                if found:
                    sections_with_chunks.add(label)
                for ch in found:
                    if ch.chunk_id in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(ch.chunk_id)
                    chunks.append(ch)

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

    return EvidenceBundle(
        chunks=chunks,
        source_quotes=source_quotes,
        sections_retrieved=sections_retrieved,
        sections_queried=labels,
        graph_modifies=graph_modifies,
        warnings=warnings,
    )


def has_insufficient_evidence(bundle: EvidenceBundle) -> bool:
    """Caller helper: skip GPT when True."""
    return bundle.insufficient_evidence
