"""Knowledge-graph client for Adaptive Tax Phase 3 calc (Neo4j or file ontology).

``FileOntologyKgClient`` mirrors the live Cypher against ontology JSON/JSONL so
unit tests and offline demos do not need Neo4j Desktop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings

# Core Phase 3 calc query (exact shape from the Phase 3 plan).
CORE_APPLICABLE_CYPHER = """
MATCH (tp:Concept {concept_id: 'resident_individual'})
MATCH (income:Concept)-[:CONTRIBUTES_TO*1..3]->(ai:Concept {concept_id: 'assessable_income'})
WHERE income.concept_id IN $income_types
OPTIONAL MATCH (ded:Concept)-[:DEDUCTED_FROM]->(ti:Concept {concept_id: 'taxable_income'})
WHERE ded.concept_id IN $claimed_deductions
OPTIONAL MATCH (ded)-[:LIMITED_BY]->(cap:Concept)
RETURN income.concept_id AS income_id,
       ded.concept_id AS ded_id,
       cap.concept_id AS cap_id,
       ti.concept_id AS taxable_id,
       tp.concept_id AS taxpayer_id
"""

# Used when there are deduction claims but no income heads (core MATCH would return 0 rows).
DEDUCTIONS_ONLY_CYPHER = """
MATCH (tp:Concept {concept_id: 'resident_individual'})
OPTIONAL MATCH (ded:Concept)-[:DEDUCTED_FROM]->(ti:Concept {concept_id: 'taxable_income'})
WHERE ded.concept_id IN $claimed_deductions
OPTIONAL MATCH (ded)-[:LIMITED_BY]->(cap:Concept)
RETURN null AS income_id,
       ded.concept_id AS ded_id,
       cap.concept_id AS cap_id,
       ti.concept_id AS taxable_id,
       tp.concept_id AS taxpayer_id
"""

# Section anchors for explainability traces (DEFINES + COVERS_RELIEF + GOVERNED_BY).
SECTION_DEFINES_CYPHER = """
MATCH (sec:Section)-[:DEFINES]->(c:Concept)
WHERE c.concept_id IN $concept_ids
RETURN c.concept_id AS concept_id, collect(DISTINCT sec.section_uid) AS section_uids
"""

SECTION_COVERS_RELIEF_CYPHER = """
MATCH (sec:Section)-[:COVERS_RELIEF]->(r:Relief)
WHERE r.concept_id IN $concept_ids OR r.relief_id IN $concept_ids
RETURN coalesce(r.concept_id, r.relief_id) AS concept_id,
       collect(DISTINCT sec.section_uid) AS section_uids
"""

SECTION_GOVERNED_BY_CYPHER = """
MATCH (c:Concept)-[:GOVERNED_BY]->(sec:Section)
WHERE c.concept_id IN $concept_ids
RETURN c.concept_id AS concept_id, collect(DISTINCT sec.section_uid) AS section_uids
"""


@dataclass(frozen=True)
class DeductionLink:
    concept_id: str
    cap_concept_id: str | None = None
    section_uids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplicableConcepts:
    """Normalized result of the Phase 3 core calc Cypher (or file equivalent)."""

    income_concept_ids: tuple[str, ...]
    deductions: tuple[DeductionLink, ...]
    income_section_uids: dict[str, tuple[str, ...]] = field(default_factory=dict)
    resident_individual_present: bool = True


UnresolvedClaimReason = Literal["concept_missing_in_kg", "no_deducted_from_edge"]

# Concepts the calculator needs in Neo4j / file ontology (graph-stats + verify).
REQUIRED_CALC_CONCEPTS: tuple[str, ...] = (
    "qualifying_payment",
    "personal_relief",
    "assessable_income",
    "taxable_income",
    "solar_panel_relief",
    "solar_panel_relief_cap",
    "rent_relief",
    "rent_relief_cap",
    "senior_citizen_interest_relief",
    "senior_citizen_interest_relief_cap",
)


@runtime_checkable
class KgClient(Protocol):
    def resolve_applicable_concepts(
        self,
        *,
        income_types: list[str],
        claimed_deductions: list[str],
    ) -> ApplicableConcepts: ...

    def classify_unresolved_claims(
        self,
        claimed_ids: list[str],
    ) -> dict[str, UnresolvedClaimReason]: ...

    def required_concept_presence(
        self,
        concept_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, bool]: ...


def bolt_uri(uri: str) -> str:
    """Prefer ``bolt://`` for Neo4j Desktop (avoids ``neo4j://`` routing retries)."""
    cleaned = (uri or "bolt://127.0.0.1:7687").strip()
    if cleaned.startswith("neo4j://"):
        return "bolt://" + cleaned[len("neo4j://") :]
    return cleaned


def open_neo4j_driver(settings: AdaptiveTaxSettings | None = None) -> Any:
    """Open a verified Neo4j driver using the shared Desktop bolt rewrite pattern."""
    from neo4j import GraphDatabase

    cfg = settings or get_adaptive_tax_settings()
    password = (cfg.NEO4J_PASSWORD or "").strip()
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is not set")
    uri = bolt_uri(cfg.NEO4J_URI or "bolt://127.0.0.1:7687")
    # Fail fast when Desktop is down so explain/evidence degrade instead of hanging.
    driver = GraphDatabase.driver(
        uri,
        auth=(cfg.NEO4J_USER or "neo4j", password),
        connection_acquisition_timeout=3.0,
        connection_timeout=3.0,
    )
    driver.verify_connectivity()
    return driver


def _uniq(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(v for v in values if v))


def _rows_to_applicable(
    rows: list[dict[str, Any]],
    *,
    income_types: list[str],
    section_map: dict[str, tuple[str, ...]] | None = None,
) -> ApplicableConcepts:
    """Collapse Cypher row cartesian products into :class:`ApplicableConcepts`."""
    section_map = section_map or {}
    incomes: list[str] = []
    ded_map: dict[str, DeductionLink] = {}
    resident = False

    for row in rows:
        if row.get("taxpayer_id") == "resident_individual":
            resident = True
        income_id = row.get("income_id")
        if income_id:
            incomes.append(str(income_id))
        ded_id = row.get("ded_id")
        if not ded_id:
            continue
        cid = str(ded_id)
        cap = row.get("cap_id")
        existing = ded_map.get(cid)
        cap_concept_id = (
            str(cap) if cap else (existing.cap_concept_id if existing else None)
        )
        sections = list(existing.section_uids) if existing else []
        sections.extend(section_map.get(cid, ()))
        if cap_concept_id:
            sections.extend(section_map.get(cap_concept_id, ()))
        ded_map[cid] = DeductionLink(
            concept_id=cid,
            cap_concept_id=cap_concept_id,
            section_uids=_uniq(sections),
        )

    # Preserve caller income order when possible.
    ordered_incomes = [i for i in income_types if i in set(incomes)]
    ordered_incomes.extend(i for i in dict.fromkeys(incomes) if i not in ordered_incomes)

    income_sections = {
        cid: section_map.get(cid, ()) for cid in ordered_incomes if section_map.get(cid)
    }

    return ApplicableConcepts(
        income_concept_ids=_uniq(ordered_incomes),
        deductions=tuple(ded_map.values()),
        income_section_uids=income_sections,
        resident_individual_present=resident,
    )


class FileOntologyKgClient:
    """In-process KG backed by ontology JSON + calc edges JSONL (unit tests / offline)."""

    def __init__(self, ontology_dir: Path | None = None) -> None:
        settings = get_adaptive_tax_settings()
        self._root = Path(ontology_dir) if ontology_dir else settings.ontology_dir
        self._concept_ids = self._load_concept_ids()
        self._edges = self._load_edges()
        # concept_id -> section_uids (DEFINES + COVERS_RELIEF via relief concept_id)
        self._section_by_concept: dict[str, list[str]] = {}
        self._contributes: dict[str, list[str]] = {}
        self._deducted_from: dict[str, list[str]] = {}
        self._limited_by: dict[str, list[str]] = {}
        self._relief_concept_by_id: dict[str, str] = {}
        self._index_reliefs()
        self._index_edges()

    def _load_concept_ids(self) -> set[str]:
        path = self._root / "concepts_mvp.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(c["concept_id"])
            for c in (doc.get("concepts") or [])
            if isinstance(c, dict) and c.get("concept_id")
        }

    def _load_edges(self) -> list[dict[str, Any]]:
        """Prefer Phase 5.10 ``calculation_edges_full.jsonl`` when present.

        Falls back to the curated MVP seed. MENTIONS and other bulk rows are
        ignored by ``_index_edges`` (only DEFINES / GOVERNED_BY / CONTRIBUTES_TO /
        DEDUCTED_FROM / LIMITED_BY affect resolve).
        """
        full = self._root / "calculation_edges_full.jsonl"
        seed = self._root / "mvp_calc_edges_seed.jsonl"
        path = full if full.is_file() and full.stat().st_size > 0 else seed
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _index_reliefs(self) -> None:
        """Map Relief.relief_id → concept_id from relief_caps.json (for COVERS_RELIEF)."""
        path = self._root / "relief_caps.json"
        if not path.is_file():
            return
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("reliefs") or []:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("relief_id") or "")
            cid = str(row.get("concept_id") or "")
            if rid and cid:
                self._relief_concept_by_id[rid] = cid

    def _add_section(self, concept_id: str, section_uid: str) -> None:
        if not concept_id or not section_uid:
            return
        bucket = self._section_by_concept.setdefault(concept_id, [])
        if section_uid not in bucket:
            bucket.append(section_uid)

    def _index_edges(self) -> None:
        for row in self._edges:
            rel = str(row.get("rel_type") or "")
            fid = str(row.get("from_id") or "")
            tid = str(row.get("to_id") or "")
            if not fid or not tid:
                continue
            if rel == "DEFINES" and str(row.get("from_label")) == "Section":
                self._add_section(tid, fid)
            elif rel == "COVERS_RELIEF" and str(row.get("from_label")) == "Section":
                concept_id = self._relief_concept_by_id.get(tid, tid)
                self._add_section(concept_id, fid)
            elif rel == "GOVERNED_BY" and str(row.get("to_label")) == "Section":
                # Concept / Relief → Section (Phase 5 provenance bridge).
                self._add_section(fid, tid)
            elif rel == "CONTRIBUTES_TO":
                self._contributes.setdefault(fid, []).append(tid)
            elif rel == "DEDUCTED_FROM":
                self._deducted_from.setdefault(fid, []).append(tid)
            elif rel == "LIMITED_BY":
                self._limited_by.setdefault(fid, []).append(tid)

    def _reaches_assessable(self, start: str, *, max_depth: int = 3) -> bool:
        """Mirror ``CONTRIBUTES_TO*1..3`` toward ``assessable_income``."""
        frontier = [(start, 0)]
        seen = {start}
        while frontier:
            node, depth = frontier.pop()
            if depth >= max_depth:
                continue
            for nxt in self._contributes.get(node, []):
                if nxt == "assessable_income":
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, depth + 1))
        return False

    def resolve_applicable_concepts(
        self,
        *,
        income_types: list[str],
        claimed_deductions: list[str],
    ) -> ApplicableConcepts:
        incomes = [
            cid
            for cid in income_types
            if cid in self._concept_ids and self._reaches_assessable(cid)
        ]

        deductions: list[DeductionLink] = []
        for cid in claimed_deductions:
            if cid not in self._concept_ids:
                continue
            targets = self._deducted_from.get(cid) or []
            if "taxable_income" not in targets:
                continue
            caps = self._limited_by.get(cid) or []
            cap_id = caps[0] if caps else None
            sections = list(self._section_by_concept.get(cid, []))
            if cap_id:
                sections.extend(self._section_by_concept.get(cap_id, []))
            deductions.append(
                DeductionLink(
                    concept_id=cid,
                    cap_concept_id=cap_id,
                    section_uids=_uniq(sections),
                )
            )

        income_sections = {
            cid: _uniq(self._section_by_concept.get(cid, []))
            for cid in incomes
            if self._section_by_concept.get(cid)
        }

        return ApplicableConcepts(
            income_concept_ids=tuple(incomes),
            deductions=tuple(deductions),
            income_section_uids=income_sections,
            resident_individual_present="resident_individual" in self._concept_ids,
        )

    def classify_unresolved_claims(
        self,
        claimed_ids: list[str],
    ) -> dict[str, UnresolvedClaimReason]:
        """Map unresolved claim ids to missing-node vs missing-DEDUCTED_FROM."""
        out: dict[str, UnresolvedClaimReason] = {}
        for cid in claimed_ids:
            if cid not in self._concept_ids:
                out[cid] = "concept_missing_in_kg"
                continue
            targets = self._deducted_from.get(cid) or []
            if "taxable_income" not in targets:
                out[cid] = "no_deducted_from_edge"
        return out

    def required_concept_presence(
        self,
        concept_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, bool]:
        ids = list(concept_ids or REQUIRED_CALC_CONCEPTS)
        return {cid: cid in self._concept_ids for cid in ids}


class Neo4jKgClient:
    """Live Neo4j Desktop / Bolt client for the Phase 3 calc Cypher."""

    def __init__(self, settings: AdaptiveTaxSettings | None = None) -> None:
        self._settings = settings or get_adaptive_tax_settings()

    def _fetch_section_map(self, session: Any, concept_ids: list[str]) -> dict[str, tuple[str, ...]]:
        if not concept_ids:
            return {}
        buckets: dict[str, list[str]] = {}
        for query in (
            SECTION_DEFINES_CYPHER,
            SECTION_COVERS_RELIEF_CYPHER,
            SECTION_GOVERNED_BY_CYPHER,
        ):
            for row in session.run(query, concept_ids=list(concept_ids)).data():
                cid = row.get("concept_id")
                if not cid:
                    continue
                bucket = buckets.setdefault(str(cid), [])
                for uid in row.get("section_uids") or []:
                    if uid and str(uid) not in bucket:
                        bucket.append(str(uid))
        return {cid: tuple(uids) for cid, uids in buckets.items()}

    def resolve_applicable_concepts(
        self,
        *,
        income_types: list[str],
        claimed_deductions: list[str],
    ) -> ApplicableConcepts:
        driver = open_neo4j_driver(self._settings)
        try:
            with driver.session() as session:
                if income_types:
                    rows = session.run(
                        CORE_APPLICABLE_CYPHER,
                        income_types=list(income_types),
                        claimed_deductions=list(claimed_deductions),
                    ).data()
                elif claimed_deductions:
                    rows = session.run(
                        DEDUCTIONS_ONLY_CYPHER,
                        claimed_deductions=list(claimed_deductions),
                    ).data()
                else:
                    rows = []

                concept_ids = {
                    *(income_types or []),
                    *(claimed_deductions or []),
                }
                for row in rows:
                    for key in ("income_id", "ded_id", "cap_id"):
                        if row.get(key):
                            concept_ids.add(str(row[key]))
                section_map = self._fetch_section_map(session, sorted(concept_ids))
        finally:
            driver.close()

        result = _rows_to_applicable(
            rows,
            income_types=list(income_types),
            section_map=section_map,
        )
        # Core query requires resident_individual; if we got rows, it was present.
        if rows and not result.resident_individual_present:
            return ApplicableConcepts(
                income_concept_ids=result.income_concept_ids,
                deductions=result.deductions,
                income_section_uids=result.income_section_uids,
                resident_individual_present=True,
            )
        return result

    def classify_unresolved_claims(
        self,
        claimed_ids: list[str],
    ) -> dict[str, UnresolvedClaimReason]:
        if not claimed_ids:
            return {}
        driver = open_neo4j_driver(self._settings)
        try:
            with driver.session() as session:
                rows = session.run(
                    """
                    UNWIND $ids AS cid
                    OPTIONAL MATCH (c:Concept {concept_id: cid})
                    OPTIONAL MATCH (c)-[:DEDUCTED_FROM]->(
                        ti:Concept {concept_id: 'taxable_income'}
                    )
                    RETURN cid AS concept_id,
                           c IS NOT NULL AS exists,
                           ti IS NOT NULL AS has_edge
                    """,
                    ids=list(claimed_ids),
                ).data()
        finally:
            driver.close()
        out: dict[str, UnresolvedClaimReason] = {}
        seen: set[str] = set()
        for row in rows:
            cid = str(row.get("concept_id") or "")
            if not cid:
                continue
            seen.add(cid)
            if not row.get("exists"):
                out[cid] = "concept_missing_in_kg"
            elif not row.get("has_edge"):
                out[cid] = "no_deducted_from_edge"
        for cid in claimed_ids:
            if cid not in seen:
                out.setdefault(cid, "concept_missing_in_kg")
        return out

    def required_concept_presence(
        self,
        concept_ids: tuple[str, ...] | list[str] | None = None,
    ) -> dict[str, bool]:
        ids = list(concept_ids or REQUIRED_CALC_CONCEPTS)
        driver = open_neo4j_driver(self._settings)
        try:
            with driver.session() as session:
                rows = session.run(
                    """
                    UNWIND $ids AS cid
                    OPTIONAL MATCH (c:Concept {concept_id: cid})
                    RETURN cid AS concept_id, c IS NOT NULL AS present
                    """,
                    ids=ids,
                ).data()
        finally:
            driver.close()
        present = {
            str(row["concept_id"]): bool(row.get("present"))
            for row in rows
            if row.get("concept_id")
        }
        return {cid: bool(present.get(cid)) for cid in ids}


def get_kg_client(
    *,
    mode: Literal["neo4j", "file", "auto"] | None = None,
    ontology_dir: Path | None = None,
) -> KgClient:
    """Factory for tests / demos / explain.

    ``auto`` (or omitted mode) → Neo4j when ``NEO4J_PASSWORD`` is set, else file
    ontology. HTTP POST /calculate does not use this default: it calls
    ``get_kg_client(mode="neo4j")`` and returns 503 if Desktop is down.
    """
    settings = get_adaptive_tax_settings()
    effective: Literal["neo4j", "file"]
    if mode is None or mode == "auto":
        effective = settings.resolve_kg_mode()
    else:
        effective = mode
    if effective == "neo4j":
        return Neo4jKgClient(settings)
    return FileOntologyKgClient(ontology_dir=ontology_dir or settings.ontology_dir)
