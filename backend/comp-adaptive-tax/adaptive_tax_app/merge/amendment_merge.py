"""Approve hook: merge approved rules into Neo4j + re-index Chroma (Phase 2)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import AmendmentJob, RuleSource, RuleVersion

_BASE_ACT_SOURCE_DOC_ID = "ird-ira-2017-base"

# Filename stem patterns → adaptive-tax corpus source_doc_id
_FILENAME_SOURCE_DOC: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"IR_Act_No[._]?02[-_]?2025", re.I), "ird-amend-2025-02"),
    (re.compile(r"IR_Act_No[._]?11[-_]?2026", re.I), "ird-amend-2026-11"),
    (re.compile(r"IR_Act_No[._]?04[-_.]?2023", re.I), "ird-amend-2023-04"),
    (re.compile(r"IR_Act_No14_?2023", re.I), "ird-amend-2023-14"),
    (re.compile(r"IR_Act_No[._]?45[-_.]?2022", re.I), "ird-amend-2022-45"),
    (re.compile(r"IR_Act_No[._]?10[-_.]?2021", re.I), "ird-amend-2021-10"),
    (re.compile(r"IR_Act_No[._]?24[-_.]?2017", re.I), "ird-ira-2017-base"),
    (re.compile(r"IRA_Cons_Act", re.I), "ird-consolidated-2025"),
    (re.compile(r"Guide to Inland Revenue", re.I), "ird-guide-ira"),
    (re.compile(r"Tax_Knowledge_Base", re.I), "ird-calc-ontology-v5"),
]

_RELIEF_BY_CONCEPT: dict[str, str] = {
    "qualifying_payment_cap": "sec52_qualifying_payment_cap",
    "qualifying_payment": "sec52_qualifying_payment_cap",
    "personal_relief": "personal_relief",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+", re.I)


@dataclass(frozen=True)
class AmendmentMergeResult:
    merged: bool
    reason: str
    amendment_job_id: uuid.UUID
    details: dict[str, Any] | None = None


def map_filename_to_source_doc_id(filename: str | None) -> str:
    name = (filename or "").strip()
    for pattern, source_doc_id in _FILENAME_SOURCE_DOC:
        if pattern.search(name):
            return source_doc_id
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    slug = _SLUG_RE.sub("-", stem).strip("-").lower() or "unknown-amendment"
    return f"ird-amend-upload-{slug[:48]}"


def make_section_uid(source_doc_id: str, section_label: str | None) -> str | None:
    if not source_doc_id or not section_label or not str(section_label).strip():
        return None
    label = str(section_label).strip()
    if not label.lower().startswith("section"):
        label = f"Section {label}"
    slug = _SLUG_RE.sub("_", label).strip("_").lower()
    if not slug:
        return None
    return f"{source_doc_id.strip()}::sec::{slug}"


def _section_targets(rule: RuleSource) -> list[str]:
    labels: list[str] = []
    for raw in (rule.amends_section, rule.section):
        if raw and str(raw).strip() and str(raw).strip() not in labels:
            labels.append(str(raw).strip())
    uids: list[str] = []
    for label in labels:
        uid = make_section_uid(_BASE_ACT_SOURCE_DOC_ID, label)
        if uid and uid not in uids:
            uids.append(uid)
    return uids


def _open_neo4j_driver() -> Any:
    from neo4j import GraphDatabase

    settings = get_adaptive_tax_settings()
    password = (settings.NEO4J_PASSWORD or "").strip()
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is not set")

    uri = (settings.NEO4J_URI or "bolt://127.0.0.1:7687").strip()
    user = settings.NEO4J_USER or "neo4j"
    # Prefer bolt for Neo4j Desktop (avoids routing retries on neo4j://).
    if uri.startswith("neo4j://"):
        uri = "bolt://" + uri[len("neo4j://") :]

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def _merge_law_instrument(tx: Any, *, source_doc_id: str, title: str) -> None:
    tx.run(
        """
        MERGE (n:LawInstrument {source_doc_id: $source_doc_id})
        SET n.title = coalesce($title, n.title),
            n.instrument_type = coalesce(n.instrument_type, 'amendment_act'),
            n.doc_type = coalesce(n.doc_type, 'pdf'),
            n.tier = coalesce(n.tier, 'A'),
            n.review_status = 'approved_merge'
        """,
        source_doc_id=source_doc_id,
        title=title,
    )


def _merge_section(tx: Any, *, section_uid: str, section_label: str) -> None:
    tx.run(
        """
        MERGE (n:Section {section_uid: $section_uid})
        SET n.section_label = coalesce(n.section_label, $section_label),
            n.source_doc_id = coalesce(n.source_doc_id, $base_doc),
            n.review_status = coalesce(n.review_status, 'approved_merge')
        WITH n
        MATCH (l:LawInstrument {source_doc_id: $base_doc})
        MERGE (n)-[:PART_OF]->(l)
        """,
        section_uid=section_uid,
        section_label=section_label,
        base_doc=_BASE_ACT_SOURCE_DOC_ID,
    )


def _merge_modifies(
    tx: Any,
    *,
    source_doc_id: str,
    section_uid: str,
    source_note: str,
    effective_from: str | None,
) -> None:
    tx.run(
        """
        MATCH (a:LawInstrument {source_doc_id: $source_doc_id})
        MATCH (s:Section {section_uid: $section_uid})
        MERGE (a)-[r:MODIFIES]->(s)
        SET r.review_status = 'approved_merge',
            r.source_note = $source_note,
            r.effective_from = $effective_from
        """,
        source_doc_id=source_doc_id,
        section_uid=section_uid,
        source_note=source_note[:500],
        effective_from=effective_from or "",
    )


def _update_relief_cap(tx: Any, *, relief_id: str, cap_amount: float, effective_from: str | None) -> None:
    tx.run(
        """
        MERGE (n:Relief {relief_id: $relief_id})
        SET n.cap_amount = $cap_amount,
            n.review_status = 'approved_merge',
            n.effective_start_date = CASE
              WHEN $effective_from <> '' THEN $effective_from
              ELSE coalesce(n.effective_start_date, '')
            END
        """,
        relief_id=relief_id,
        cap_amount=float(cap_amount),
        effective_from=effective_from or "",
    )


def _chroma_reindex_quotes(
    *,
    source_doc_id: str,
    rules: list[RuleSource],
    section_uids: list[str],
) -> dict[str, Any]:
    try:
        from adaptive_tax_app.services.chroma_index import get_chroma_index
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"chroma_import:{exc}"}

    rows: list[dict[str, Any]] = []
    for rule in rules:
        quote = (rule.source_quote or "").strip()
        if not quote:
            continue
        section = (rule.amends_section or rule.section or "").strip() or "unknown"
        chunk_id = f"{source_doc_id}::approve::{rule.id}"
        rows.append(
            {
                "chunk_id": chunk_id,
                "source_doc_id": source_doc_id,
                "section_ref": f"Section {section}",
                "page": 0,
                "text": quote,
            }
        )

    # Also re-upsert any corpus chunks already mentioning these section numbers.
    try:
        index = get_chroma_index()
        written = index.upsert_chunks(rows) if rows else 0
        return {
            "ok": True,
            "quote_chunks_upserted": written,
            "section_uids": section_uids,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "quote_chunks_upserted": 0}


def merge_approved_amendment(
    *,
    db: Session,
    amendment_job_id: uuid.UUID,
    rule_sources: list[RuleSource],
    rule_versions: list[RuleVersion] | None = None,
) -> AmendmentMergeResult:
    """Merge approved rules into Neo4j + Chroma.

    Postgres ``rule_versions`` are already written by the approve path. This
    function never raises for Neo4j/Chroma failures — it returns
    ``merged=False`` with ``reason='neo4j_unavailable'`` (or partial).
    """
    _ = db  # reserved for future merge audit rows
    job = None
    try:
        job = db.get(AmendmentJob, amendment_job_id)
    except Exception:  # noqa: BLE001
        job = None

    filename = getattr(job, "original_filename", None) if job is not None else None
    source_doc_id = map_filename_to_source_doc_id(filename)
    title = filename or source_doc_id

    details: dict[str, Any] = {
        "source_doc_id": source_doc_id,
        "rule_source_ids": [str(r.id) for r in rule_sources],
        "rule_version_ids": [str(v.id) for v in (rule_versions or [])],
        "modifies": [],
        "relief_updates": [],
        "chroma": None,
    }

    try:
        driver = _open_neo4j_driver()
    except Exception as exc:  # noqa: BLE001
        return AmendmentMergeResult(
            merged=False,
            reason="neo4j_unavailable",
            amendment_job_id=amendment_job_id,
            details={**details, "error": str(exc)},
        )

    modifies: list[str] = []
    relief_updates: list[dict[str, Any]] = []
    try:
        with driver.session() as session:
            session.execute_write(
                _merge_law_instrument,
                source_doc_id=source_doc_id,
                title=str(title),
            )

            for rule in rule_sources:
                eff: str | None = None
                if isinstance(rule.effective_date, date):
                    eff = rule.effective_date.isoformat()
                note = (rule.source_quote or f"Approved merge for section {rule.section}")[:500]

                for section_uid in _section_targets(rule):
                    label = rule.amends_section or rule.section or section_uid
                    session.execute_write(
                        _merge_section,
                        section_uid=section_uid,
                        section_label=f"Section {label}" if not str(label).lower().startswith("section") else str(label),
                    )
                    session.execute_write(
                        _merge_modifies,
                        source_doc_id=source_doc_id,
                        section_uid=section_uid,
                        source_note=note,
                        effective_from=eff,
                    )
                    if section_uid not in modifies:
                        modifies.append(section_uid)

                concept = (rule.concept_id or "").strip()
                relief_id = _RELIEF_BY_CONCEPT.get(concept)
                if relief_id and rule.maximum is not None:
                    session.execute_write(
                        _update_relief_cap,
                        relief_id=relief_id,
                        cap_amount=float(rule.maximum),
                        effective_from=eff,
                    )
                    relief_updates.append(
                        {"relief_id": relief_id, "cap_amount": float(rule.maximum), "concept_id": concept}
                    )
    except Exception as exc:  # noqa: BLE001
        return AmendmentMergeResult(
            merged=False,
            reason="neo4j_unavailable",
            amendment_job_id=amendment_job_id,
            details={**details, "error": str(exc)},
        )
    finally:
        driver.close()

    details["modifies"] = modifies
    details["relief_updates"] = relief_updates
    chroma_info = _chroma_reindex_quotes(
        source_doc_id=source_doc_id,
        rules=rule_sources,
        section_uids=modifies,
    )
    details["chroma"] = chroma_info

    if not modifies:
        return AmendmentMergeResult(
            merged=False,
            reason="no_section_targets",
            amendment_job_id=amendment_job_id,
            details=details,
        )

    reason = "ok" if chroma_info.get("ok") else "partial"
    return AmendmentMergeResult(
        merged=True,
        reason=reason,
        amendment_job_id=amendment_job_id,
        details=details,
    )
