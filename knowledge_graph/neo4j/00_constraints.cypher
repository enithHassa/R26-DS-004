// Phase 3 Step 5 — uniqueness constraints (Neo4j 5+ syntax)
// Apply before bulk load. Matches ontology_v1.json id_property per label.

CREATE CONSTRAINT lawinstrument_source_doc_id_unique IF NOT EXISTS
FOR (n:LawInstrument)
REQUIRE n.source_doc_id IS UNIQUE;

CREATE CONSTRAINT section_section_uid_unique IF NOT EXISTS
FOR (n:Section)
REQUIRE n.section_uid IS UNIQUE;

CREATE CONSTRAINT textchunk_chunk_id_unique IF NOT EXISTS
FOR (n:TextChunk)
REQUIRE n.chunk_id IS UNIQUE;

CREATE CONSTRAINT concept_concept_id_unique IF NOT EXISTS
FOR (n:Concept)
REQUIRE n.concept_id IS UNIQUE;

CREATE CONSTRAINT relief_relief_id_unique IF NOT EXISTS
FOR (n:Relief)
REQUIRE n.relief_id IS UNIQUE;

CREATE CONSTRAINT rateband_rate_band_id_unique IF NOT EXISTS
FOR (n:RateBand)
REQUIRE n.rate_band_id IS UNIQUE;

CREATE CONSTRAINT proceduremilestone_milestone_id_unique IF NOT EXISTS
FOR (n:ProcedureMilestone)
REQUIRE n.milestone_id IS UNIQUE;

CREATE CONSTRAINT irdhubsummary_summary_id_unique IF NOT EXISTS
FOR (n:IrdHubSummary)
REQUIRE n.summary_id IS UNIQUE;

CREATE CONSTRAINT consolidatedviewpassage_anchor_id_unique IF NOT EXISTS
FOR (n:ConsolidatedViewPassage)
REQUIRE n.anchor_id IS UNIQUE;
