"""Phase 4 — GraphService: async Neo4j interface for knowledge graph enrichment.

Instantiated once in lifespan and stored on app.state.graph_service.
All Cypher uses parameterized queries — never string-interpolated user input.
"""

from __future__ import annotations

from backend.shared.utils.logging import logger

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    AsyncDriver = None  # type: ignore[assignment,misc]

from app.schemas.graph_v1 import (
    ConceptNode,
    GraphContext,
    LexNote,
    ProcedureMilestoneNode,
    RateBandNode,
    ReliefNode,
    TaxpayerProfileNode,
)

# ---------------------------------------------------------------------------
# Parameterized Cypher constants
# ---------------------------------------------------------------------------

_CHUNKS_TO_CONTEXT = """\
MATCH (t:TextChunk)
WHERE t.chunk_id IN $chunk_ids
OPTIONAL MATCH (t)-[:MENTIONS]->(c:Concept)
OPTIONAL MATCH (inst:LawInstrument)-[:HAS_CHUNK]->(t)
OPTIONAL MATCH (newer:LawInstrument)-[:SUPERSEDES]->(inst)
OPTIONAL MATCH (sec:Section)-[:HAS_CHUNK]->(t)
OPTIONAL MATCH (sec)-[:COVERS_RELIEF]->(r:Relief)
OPTIONAL MATCH (rb:RateBand)-[:APPLIES_TO]->(c)
OPTIONAL MATCH (pm:ProcedureMilestone)-[:DERIVED_FROM]->(sec)
RETURN
  collect(DISTINCT c)    AS concepts,
  collect(DISTINCT r)    AS reliefs,
  collect(DISTINCT rb)   AS rate_bands,
  collect(DISTINCT pm)   AS milestones,
  collect(DISTINCT newer.source_doc_id) AS superseded_by
"""

_RELIEF_PROFILES = """\
MATCH (tp:TaxpayerProfile)-[:RELEVANT_RELIEF]->(r:Relief)
WHERE r.relief_id IN $relief_ids
RETURN DISTINCT tp
LIMIT 10
"""

_LEX_OVERRIDES = """\
MATCH (s1:Section)-[:OVERRIDES]->(s2:Section)
WHERE s1.section_uid IN $section_uids OR s2.section_uid IN $section_uids
RETURN s1.section_uid AS winner, s2.section_uid AS overridden,
       s1.authority_class AS authority_class
LIMIT 10
"""

_INTENT_RELIEF = """\
MATCH (r:Relief {relief_id: $relief_id})
OPTIONAL MATCH (sec:Section)-[:COVERS_RELIEF]->(r)
OPTIONAL MATCH (rb:RateBand)-[:APPLIES_TO]->(c:Concept)
OPTIONAL MATCH (tp:TaxpayerProfile)-[:RELEVANT_RELIEF]->(r)
RETURN r, collect(DISTINCT rb) AS rate_bands,
       collect(DISTINCT tp) AS profiles
LIMIT 1
"""

_INTENT_CONCEPT = """\
MATCH (c:Concept {concept_id: $concept_id})
OPTIONAL MATCH (rb:RateBand)-[:APPLIES_TO]->(c)
OPTIONAL MATCH (tp:TaxpayerProfile)-[:RELEVANT_CONCEPT]->(c)
RETURN c, collect(DISTINCT rb) AS rate_bands,
       collect(DISTINCT tp) AS profiles
LIMIT 1
"""


# ---------------------------------------------------------------------------
# Node → Pydantic helpers
# ---------------------------------------------------------------------------

def _to_concept(node) -> ConceptNode:
    p = dict(node.items())
    return ConceptNode(
        concept_id=p.get("concept_id", ""),
        canonical_name=p.get("canonical_name"),
        aliases=p.get("aliases") or [],
        notes=p.get("notes"),
    )


def _to_relief(node) -> ReliefNode:
    p = dict(node.items())
    return ReliefNode(
        relief_id=p.get("relief_id", ""),
        display_name=p.get("display_name"),
        statutory_label=p.get("statutory_label"),
        description=p.get("description"),
        source_doc_id=p.get("source_doc_id"),
    )


def _to_rate_band(node) -> RateBandNode:
    p = dict(node.items())
    return RateBandNode(
        rate_band_id=p.get("rate_band_id", ""),
        band_label=p.get("band_label"),
        band_type=p.get("band_type"),
        lower_bound=p.get("lower_bound"),
        upper_bound=p.get("upper_bound"),
        rate_percent=p.get("rate_percent"),
        currency=p.get("currency", "LKR"),
        effective_start_date=p.get("effective_start_date"),
        effective_end_date=p.get("effective_end_date"),
    )


def _to_milestone(node) -> ProcedureMilestoneNode:
    p = dict(node.items())
    return ProcedureMilestoneNode(
        milestone_id=p.get("milestone_id", ""),
        milestone_kind=p.get("milestone_kind"),
        display_name=p.get("display_name"),
        description=p.get("description"),
        due_day=p.get("due_day"),
        due_month=p.get("due_month"),
        recurrence=p.get("recurrence"),
        applies_to=p.get("applies_to") or [],
    )


def _to_profile(node) -> TaxpayerProfileNode:
    p = dict(node.items())
    return TaxpayerProfileNode(
        profile_type=p.get("profile_type", ""),
        display_name=p.get("display_name"),
        description=p.get("description"),
    )


def _dedupe(items: list, key: str) -> list:
    seen: set = set()
    out = []
    for item in items:
        v = getattr(item, key, None)
        if v and v not in seen:
            seen.add(v)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# GraphService
# ---------------------------------------------------------------------------

class GraphService:
    """Async interface to Neo4j knowledge graph for retrieval enrichment."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        if not _NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver not installed. Run: pip install neo4j>=5.14.0,<6")
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    async def close(self) -> None:
        await self._driver.close()

    async def verify(self) -> bool:
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("GraphService connectivity check failed: {}", exc)
            return False

    # ------------------------------------------------------------------
    # Core enrichment — called by routers
    # ------------------------------------------------------------------

    async def enrich_from_chunks(
        self,
        chunk_ids: list[str],
        section_uids: list[str] | None = None,
    ) -> GraphContext:
        """Return graph context for a set of retrieved chunk_ids."""
        if not chunk_ids:
            return GraphContext()

        try:
            async with self._driver.session(database=self._database) as s:
                result = await s.run(_CHUNKS_TO_CONTEXT, chunk_ids=chunk_ids)
                record = await result.single()

            if record is None:
                return GraphContext()

            concepts   = [_to_concept(n)   for n in (record["concepts"]   or []) if n]
            reliefs    = [_to_relief(n)    for n in (record["reliefs"]    or []) if n]
            rate_bands = [_to_rate_band(n) for n in (record["rate_bands"] or []) if n]
            milestones = [_to_milestone(n) for n in (record["milestones"] or []) if n]
            superseded_by = [v for v in (record["superseded_by"] or []) if v]

            # Fetch profiles linked to found reliefs
            profiles: list[TaxpayerProfileNode] = []
            if reliefs:
                relief_ids = [r.relief_id for r in reliefs]
                profiles = await self._profiles_for_reliefs(relief_ids)

            # Lex specialis overrides
            lex_notes: list[LexNote] = []
            if section_uids:
                lex_notes = await self._lex_notes(section_uids)

            return GraphContext(
                concepts=_dedupe(concepts, "concept_id"),
                reliefs=_dedupe(reliefs, "relief_id"),
                rate_bands=_dedupe(rate_bands, "rate_band_id"),
                procedure_milestones=_dedupe(milestones, "milestone_id"),
                taxpayer_profiles=_dedupe(profiles, "profile_type"),
                superseded_by=list(dict.fromkeys(superseded_by)),
                lex_notes=lex_notes,
            )

        except Exception as exc:
            logger.warning("GraphService.enrich_from_chunks failed: {}", exc)
            return GraphContext()

    async def enrich_from_intent(self, intent: str | None) -> GraphContext:
        """Return graph context based on predicted NLU intent."""
        if not intent or intent == "_default":
            return GraphContext()

        # Intent → graph map
        _INTENT_MAP: dict[str, dict] = {
            "personal_relief":  {"query": _INTENT_RELIEF,   "param": {"relief_id":  "relief_personal"}},
            "donation_relief":  {"query": _INTENT_RELIEF,   "param": {"relief_id":  "donation_relief"}},
            "residence_scope":  {"query": _INTENT_CONCEPT,  "param": {"concept_id": "tax_resident"}},
            "income_tax_rates": {"query": _INTENT_CONCEPT,  "param": {"concept_id": "taxable_income"}},
            "filing_deadline":  {"query": _INTENT_CONCEPT,  "param": {"concept_id": "year_of_assessment"}},
            "withholding_tax":  {"query": _INTENT_CONCEPT,  "param": {"concept_id": "withholding_tax"}},
        }

        entry = _INTENT_MAP.get(intent)
        if entry is None:
            return GraphContext()

        try:
            async with self._driver.session(database=self._database) as s:
                result = await s.run(entry["query"], **entry["param"])
                record = await result.single()

            if record is None:
                return GraphContext()

            reliefs: list[ReliefNode] = []
            rate_bands: list[RateBandNode] = []
            profiles: list[TaxpayerProfileNode] = []

            if "r" in record.keys() and record["r"]:
                reliefs = [_to_relief(record["r"])]
            rate_bands = [_to_rate_band(n) for n in (record.get("rate_bands") or []) if n]
            profiles   = [_to_profile(n)   for n in (record.get("profiles")   or []) if n]

            return GraphContext(
                reliefs=reliefs,
                rate_bands=_dedupe(rate_bands, "rate_band_id"),
                taxpayer_profiles=_dedupe(profiles, "profile_type"),
            )

        except Exception as exc:
            logger.warning("GraphService.enrich_from_intent failed (intent={}): {}", intent, exc)
            return GraphContext()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _profiles_for_reliefs(self, relief_ids: list[str]) -> list[TaxpayerProfileNode]:
        try:
            async with self._driver.session(database=self._database) as s:
                result = await s.run(_RELIEF_PROFILES, relief_ids=relief_ids)
                return [_to_profile(r["tp"]) async for r in result if r["tp"]]
        except Exception as exc:
            logger.warning("GraphService._profiles_for_reliefs failed: {}", exc)
            return []

    async def _lex_notes(self, section_uids: list[str]) -> list[LexNote]:
        try:
            async with self._driver.session(database=self._database) as s:
                result = await s.run(_LEX_OVERRIDES, section_uids=section_uids)
                notes = []
                async for r in result:
                    notes.append(LexNote(
                        winner_section_uid=r["winner"],
                        overridden_section_uid=r["overridden"],
                        authority_class=r["authority_class"],
                        note=f"{r['winner']} overrides {r['overridden']}",
                    ))
                return notes
        except Exception as exc:
            logger.warning("GraphService._lex_notes failed: {}", exc)
            return []


def _merge_contexts(a: GraphContext, b: GraphContext) -> GraphContext:
    """Merge two GraphContext objects — union of all lists, deduped."""
    return GraphContext(
        concepts          =_dedupe(a.concepts + b.concepts, "concept_id"),
        reliefs           =_dedupe(a.reliefs + b.reliefs, "relief_id"),
        rate_bands        =_dedupe(a.rate_bands + b.rate_bands, "rate_band_id"),
        procedure_milestones=_dedupe(
            a.procedure_milestones + b.procedure_milestones, "milestone_id"
        ),
        taxpayer_profiles =_dedupe(a.taxpayer_profiles + b.taxpayer_profiles, "profile_type"),
        superseded_by     =list(dict.fromkeys(a.superseded_by + b.superseded_by)),
        lex_notes         =a.lex_notes + b.lex_notes,
    )
