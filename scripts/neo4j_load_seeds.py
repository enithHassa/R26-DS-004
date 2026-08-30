#!/usr/bin/env python3
"""Phase 4 seed loader — loads Concept, Relief, RateBand, ProcedureMilestone,
TaxpayerProfile, and IrdHubSummary nodes plus all their relationships into Neo4j.

Env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Install neo4j driver: pip install neo4j>=5.14.0,<6", file=sys.stderr)
    raise SystemExit(2) from None


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _driver():
    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    return GraphDatabase.driver(uri, auth=(user, password))


def _db():
    return os.environ.get("NEO4J_DATABASE", "neo4j")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_concepts(session, concepts: list[dict]) -> int:
    count = 0
    for c in concepts:
        session.run(
            """
            MERGE (n:Concept {concept_id: $concept_id})
            SET n.canonical_name  = $canonical_name,
                n.aliases         = $aliases,
                n.notes           = $notes,
                n.review_status   = $review_status
            """,
            concept_id=c["concept_id"],
            canonical_name=c.get("canonical_name", c["concept_id"]),
            aliases=c.get("aliases", []),
            notes=c.get("notes", ""),
            review_status=c.get("review_status", "seed"),
        )
        count += 1
    return count


def load_reliefs(session, reliefs: list[dict]) -> int:
    count = 0
    for r in reliefs:
        session.run(
            """
            MERGE (n:Relief {relief_id: $relief_id})
            SET n.display_name      = $display_name,
                n.statutory_label   = $statutory_label,
                n.description       = $description,
                n.applies_to_profile= $applies_to_profile,
                n.source_doc_id     = $source_doc_id,
                n.review_status     = $review_status
            """,
            relief_id=r["relief_id"],
            display_name=r.get("display_name", r["relief_id"]),
            statutory_label=r.get("statutory_label", ""),
            description=r.get("description", ""),
            applies_to_profile=r.get("applies_to_profile", []),
            source_doc_id=r.get("source_doc_id", ""),
            review_status=r.get("review_status", "seed"),
        )
        count += 1
    return count


def load_rate_bands(session, bands: list[dict]) -> int:
    count = 0
    for b in bands:
        session.run(
            """
            MERGE (n:RateBand {rate_band_id: $rate_band_id})
            SET n.band_label            = $band_label,
                n.band_type             = $band_type,
                n.lower_bound           = $lower_bound,
                n.upper_bound           = $upper_bound,
                n.rate_percent          = $rate_percent,
                n.currency              = $currency,
                n.effective_start_date  = $effective_start_date,
                n.effective_end_date    = $effective_end_date,
                n.source_doc_id         = $source_doc_id,
                n.review_status         = $review_status
            """,
            rate_band_id=b["rate_band_id"],
            band_label=b.get("band_label", ""),
            band_type=b.get("band_type", ""),
            lower_bound=b.get("lower_bound"),
            upper_bound=b.get("upper_bound"),
            rate_percent=b.get("rate_percent"),
            currency=b.get("currency", "LKR"),
            effective_start_date=b.get("effective_start_date"),
            effective_end_date=b.get("effective_end_date"),
            source_doc_id=b.get("source_doc_id", ""),
            review_status=b.get("review_status", "seed"),
        )
        count += 1
    return count


def load_procedure_milestones(session, milestones: list[dict]) -> int:
    count = 0
    for m in milestones:
        session.run(
            """
            MERGE (n:ProcedureMilestone {milestone_id: $milestone_id})
            SET n.milestone_kind        = $milestone_kind,
                n.display_name          = $display_name,
                n.description           = $description,
                n.due_day               = $due_day,
                n.due_month             = $due_month,
                n.recurrence            = $recurrence,
                n.applies_to            = $applies_to,
                n.return_type           = $return_type,
                n.e_service_step        = $e_service_step,
                n.effective_start_date  = $effective_start_date,
                n.effective_end_date    = $effective_end_date,
                n.source_doc_id         = $source_doc_id,
                n.review_status         = $review_status
            """,
            milestone_id=m["milestone_id"],
            milestone_kind=m.get("milestone_kind", ""),
            display_name=m.get("display_name", m["milestone_id"]),
            description=m.get("description", ""),
            due_day=m.get("due_day"),
            due_month=m.get("due_month"),
            recurrence=m.get("recurrence", "annual"),
            applies_to=m.get("applies_to", []),
            return_type=m.get("return_type", ""),
            e_service_step=m.get("e_service_step", ""),
            effective_start_date=m.get("effective_start_date"),
            effective_end_date=m.get("effective_end_date"),
            source_doc_id=m.get("source_doc_id", ""),
            review_status=m.get("review_status", "seed"),
        )
        count += 1
    return count


def load_taxpayer_profiles(session, profiles: list[dict]) -> int:
    count = 0
    for p in profiles:
        session.run(
            """
            MERGE (n:TaxpayerProfile {profile_type: $profile_type})
            SET n.display_name   = $display_name,
                n.description    = $description,
                n.review_status  = $review_status
            """,
            profile_type=p["profile_type"],
            display_name=p.get("display_name", p["profile_type"]),
            description=p.get("description", ""),
            review_status=p.get("review_status", "seed"),
        )
        count += 1
    return count


def load_ird_hub_summaries(session, summaries: list[dict]) -> int:
    count = 0
    for s in summaries:
        session.run(
            """
            MERGE (n:IrdHubSummary {summary_id: $summary_id})
            SET n.topic_label       = $topic_label,
                n.summary_text      = $summary_text,
                n.source_url        = $source_url,
                n.captured_at_utc   = $captured_at_utc,
                n.authority_weight  = $authority_weight,
                n.review_status     = $review_status
            """,
            summary_id=s["summary_id"],
            topic_label=s.get("topic_label", ""),
            summary_text=s.get("summary_text", ""),
            source_url=s.get("source_url", ""),
            captured_at_utc=s.get("captured_at_utc", ""),
            authority_weight=s.get("authority_weight", 0.55),
            review_status=s.get("review_status", "seed"),
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Relationship builders
# ---------------------------------------------------------------------------

def build_rateband_applies_to(session, bands: list[dict]) -> int:
    count = 0
    for b in bands:
        cid = b.get("applies_to_concept_id")
        if cid:
            result = session.run(
                """
                MATCH (rb:RateBand {rate_band_id: $rb_id})
                MATCH (c:Concept {concept_id: $c_id})
                MERGE (rb)-[:APPLIES_TO]->(c)
                RETURN rb.rate_band_id
                """,
                rb_id=b["rate_band_id"],
                c_id=cid,
            )
            if result.single():
                count += 1
    return count


def build_milestone_derived_from(session, milestones: list[dict]) -> int:
    count = 0
    for m in milestones:
        sec_uid = m.get("section_uid")
        if sec_uid:
            result = session.run(
                """
                MATCH (pm:ProcedureMilestone {milestone_id: $m_id})
                MATCH (s:Section {section_uid: $s_uid})
                MERGE (pm)-[:DERIVED_FROM]->(s)
                RETURN pm.milestone_id
                """,
                m_id=m["milestone_id"],
                s_uid=sec_uid,
            )
            if result.single():
                count += 1
    return count


def build_profile_relevant_relief(session, profiles: list[dict]) -> int:
    count = 0
    for p in profiles:
        for r_id in p.get("relevant_relief_ids", []):
            result = session.run(
                """
                MATCH (tp:TaxpayerProfile {profile_type: $p_type})
                MATCH (r:Relief {relief_id: $r_id})
                MERGE (tp)-[:RELEVANT_RELIEF]->(r)
                RETURN tp.profile_type
                """,
                p_type=p["profile_type"],
                r_id=r_id,
            )
            if result.single():
                count += 1
    return count


def build_profile_relevant_milestone(session, profiles: list[dict]) -> int:
    count = 0
    for p in profiles:
        for m_id in p.get("relevant_milestone_ids", []):
            result = session.run(
                """
                MATCH (tp:TaxpayerProfile {profile_type: $p_type})
                MATCH (pm:ProcedureMilestone {milestone_id: $m_id})
                MERGE (tp)-[:RELEVANT_MILESTONE]->(pm)
                RETURN tp.profile_type
                """,
                p_type=p["profile_type"],
                m_id=m_id,
            )
            if result.single():
                count += 1
    return count


def build_profile_relevant_concept(session, profiles: list[dict]) -> int:
    count = 0
    for p in profiles:
        for c_id in p.get("relevant_concept_ids", []):
            result = session.run(
                """
                MATCH (tp:TaxpayerProfile {profile_type: $p_type})
                MATCH (c:Concept {concept_id: $c_id})
                MERGE (tp)-[:RELEVANT_CONCEPT]->(c)
                RETURN tp.profile_type
                """,
                p_type=p["profile_type"],
                c_id=c_id,
            )
            if result.single():
                count += 1
    return count


def build_section_defines_concept(session) -> int:
    """Wire known sections to concepts they define based on section labels."""
    mappings = [
        ("ird-ira-2017::sec::section_2",      "tax_resident"),
        ("ird-ira-2017::sec::section_2",      "gross_income"),
        ("ird-ira-2017::sec::section_2",      "employment_income"),
        ("ird-ira-2017::sec::section_2",      "business_income"),
        ("ird-ira-2017::sec::section_2",      "investment_income"),
        ("ird-ira-2017::sec::section_2",      "assessable_income"),
        ("ird-ira-2017::sec::section_2",      "year_of_assessment"),
        ("ird-ira-2017::sec::section_9",      "withholding_tax"),
        ("ird-ira-2017::sec::section_9",      "employment_income"),
        ("ird-ira-2017::sec::second_schedule","qualifying_payment"),
        ("ird-ira-2017::sec::second_schedule","exempted_income"),
        ("ird-ira-2017::sec::schedule_exempt","exempted_income"),
        ("ird-ira-2017::sec::part_i",         "taxable_income"),
        ("ird-ira-2017::sec::part_ii",        "taxable_income"),
        ("ird-ira-consolidated-2025::sec::section_2",       "tax_resident"),
        ("ird-ira-consolidated-2025::sec::section_2",       "gross_income"),
        ("ird-ira-consolidated-2025::sec::section_9",       "withholding_tax"),
        ("ird-ira-consolidated-2025::sec::part_i",          "taxable_income"),
        ("ird-ira-consolidated-2025::sec::part_ii",         "taxable_income"),
        ("ird-ira-consolidated-2025::sec::schedule_applies","qualifying_payment"),
    ]
    count = 0
    for sec_uid, concept_id in mappings:
        result = session.run(
            """
            MATCH (s:Section {section_uid: $s_uid})
            MATCH (c:Concept {concept_id: $c_id})
            MERGE (s)-[:DEFINES]->(c)
            RETURN s.section_uid
            """,
            s_uid=sec_uid,
            c_id=concept_id,
        )
        if result.single():
            count += 1
    return count


def build_section_covers_relief(session) -> int:
    """Wire known sections to the reliefs they authorise."""
    mappings = [
        ("ird-ira-2017::sec::second_schedule",               "relief_personal"),
        ("ird-ira-2017::sec::second_schedule",               "donation_relief"),
        ("ird-ira-2017::sec::second_schedule",               "life_insurance_relief"),
        ("ird-ira-2017::sec::second_schedule",               "health_insurance_relief"),
        ("ird-ira-2017::sec::second_schedule",               "rent_relief"),
        ("ird-ira-2017::sec::second_schedule",               "home_loan_interest_relief"),
        ("ird-ira-2017::sec::second_schedule",               "retirement_contribution_relief"),
        ("ird-ira-2017::sec::part_i",                        "employment_expenses_relief"),
        ("ird-ira-consolidated-2025::sec::schedule_applies", "relief_personal"),
        ("ird-ira-consolidated-2025::sec::schedule_applies", "donation_relief"),
        ("ird-ira-consolidated-2025::sec::schedule_applies", "life_insurance_relief"),
        ("ird-ira-consolidated-2025::sec::schedule_applies", "health_insurance_relief"),
    ]
    count = 0
    for sec_uid, relief_id in mappings:
        result = session.run(
            """
            MATCH (s:Section {section_uid: $s_uid})
            MATCH (r:Relief {relief_id: $r_id})
            MERGE (s)-[:COVERS_RELIEF]->(r)
            RETURN s.section_uid
            """,
            s_uid=sec_uid,
            r_id=relief_id,
        )
        if result.single():
            count += 1
    return count


def build_supersedes_edges(session) -> int:
    """Wire amendment instruments as superseding the original IRA 2017 sections."""
    edges = [
        ("ird-ira-amend-10-2021", "ird-ira-2017"),
        ("ird-ira-amend-45-2022", "ird-ira-2017"),
        ("ird-ira-amend-04-2023", "ird-ira-2017"),
        ("ird-ira-amend-14-2023", "ird-ira-2017"),
        ("ird-ira-amend-02-2025", "ird-ira-2017"),
        ("ird-ira-consolidated-2025", "ird-ira-2017"),
    ]
    count = 0
    for newer, older in edges:
        result = session.run(
            """
            MATCH (n:LawInstrument {source_doc_id: $newer})
            MATCH (o:LawInstrument {source_doc_id: $older})
            MERGE (n)-[:SUPERSEDES]->(o)
            RETURN n.source_doc_id
            """,
            newer=newer,
            older=older,
        )
        if result.single():
            count += 1
    return count


def build_mentions_heuristic(session) -> int:
    """Create MENTIONS edges from TextChunk to Concept based on alias keyword matching."""
    concepts_result = session.run(
        "MATCH (c:Concept) RETURN c.concept_id, c.canonical_name, c.aliases"
    )
    concepts = [
        {
            "concept_id": row["c.concept_id"],
            "canonical_name": row["c.canonical_name"],
            "aliases": row["c.aliases"] or [],
        }
        for row in concepts_result
    ]

    total = 0
    for concept in concepts:
        keywords = [concept["canonical_name"].lower()] + [
            a.lower() for a in concept["aliases"]
        ]
        for kw in keywords:
            result = session.run(
                """
                MATCH (t:TextChunk)
                WHERE toLower(t.text) CONTAINS $keyword
                WITH t LIMIT 50
                MATCH (c:Concept {concept_id: $concept_id})
                MERGE (t)-[:MENTIONS]->(c)
                RETURN count(t) AS n
                """,
                keyword=kw,
                concept_id=concept["concept_id"],
            )
            row = result.single()
            if row:
                total += row["n"]

    return total


def build_hub_cites_chunks(session, summaries: list[dict]) -> int:
    """Link IrdHubSummary nodes to TextChunks they cite."""
    count = 0
    for s in summaries:
        for chunk_id in s.get("cites_chunk_ids", []):
            result = session.run(
                """
                MATCH (h:IrdHubSummary {summary_id: $s_id})
                MATCH (t:TextChunk {chunk_id: $c_id})
                MERGE (h)-[:CITES]->(t)
                RETURN h.summary_id
                """,
                s_id=s["summary_id"],
                c_id=chunk_id,
            )
            if result.single():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    seeds_dir = _REPO / "knowledge_graph" / "seeds"

    concepts   = _load_json(seeds_dir / "concepts_seed.json")
    reliefs    = _load_json(seeds_dir / "reliefs_seed.json")
    bands      = _load_json(seeds_dir / "rate_bands_seed.json")
    milestones = _load_json(seeds_dir / "procedure_milestones_seed.json")
    profiles   = _load_json(seeds_dir / "taxpayer_profiles_seed.json")
    summaries  = _load_json(seeds_dir / "ird_hub_summaries_seed.json")

    driver = _driver()
    db = _db()

    with driver.session(database=db) as session:
        # --- Node loading ---
        n = load_concepts(session, concepts)
        print(f"  Concepts loaded:              {n}")

        n = load_reliefs(session, reliefs)
        print(f"  Reliefs loaded:               {n}")

        n = load_rate_bands(session, bands)
        print(f"  RateBands loaded:             {n}")

        n = load_procedure_milestones(session, milestones)
        print(f"  ProcedureMilestones loaded:   {n}")

        n = load_taxpayer_profiles(session, profiles)
        print(f"  TaxpayerProfiles loaded:      {n}")

        n = load_ird_hub_summaries(session, summaries)
        print(f"  IrdHubSummaries loaded:       {n}")

        # --- Relationship building ---
        print()
        n = build_section_defines_concept(session)
        print(f"  DEFINES edges created:        {n}")

        n = build_section_covers_relief(session)
        print(f"  COVERS_RELIEF edges created:  {n}")

        n = build_rateband_applies_to(session, bands)
        print(f"  APPLIES_TO edges created:     {n}")

        n = build_milestone_derived_from(session, milestones)
        print(f"  DERIVED_FROM edges created:   {n}")

        n = build_supersedes_edges(session)
        print(f"  SUPERSEDES edges created:     {n}")

        n = build_profile_relevant_relief(session, profiles)
        print(f"  RELEVANT_RELIEF edges:        {n}")

        n = build_profile_relevant_milestone(session, profiles)
        print(f"  RELEVANT_MILESTONE edges:     {n}")

        n = build_profile_relevant_concept(session, profiles)
        print(f"  RELEVANT_CONCEPT edges:       {n}")

        n = build_hub_cites_chunks(session, summaries)
        print(f"  CITES edges created:          {n}")

        print()
        print("  Running heuristic MENTIONS edges (may take a moment)...")
        n = build_mentions_heuristic(session)
        print(f"  MENTIONS edges created:       {n}")

    driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
