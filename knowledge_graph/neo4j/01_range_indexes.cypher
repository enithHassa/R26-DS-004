// Phase 3 Step 5 — range indexes for common filters (Neo4j 5+)
// Uniqueness constraints already index id properties; these speed traversal / MATCH filters.

CREATE INDEX lawinstrument_tier IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.tier);

CREATE INDEX lawinstrument_instrument_type IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.instrument_type);

CREATE INDEX lawinstrument_effective_start IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.effective_start_date);

CREATE INDEX textchunk_source_doc_id IF NOT EXISTS
FOR (n:TextChunk)
ON (n.source_doc_id);

CREATE INDEX textchunk_tier IF NOT EXISTS
FOR (n:TextChunk)
ON (n.tier);

CREATE INDEX textchunk_instrument_type IF NOT EXISTS
FOR (n:TextChunk)
ON (n.instrument_type);

CREATE INDEX textchunk_effective_from IF NOT EXISTS
FOR (n:TextChunk)
ON (n.effective_from);

CREATE INDEX textchunk_content_kind IF NOT EXISTS
FOR (n:TextChunk)
ON (n.content_kind);

CREATE INDEX section_source_doc_id IF NOT EXISTS
FOR (n:Section)
ON (n.source_doc_id);

CREATE INDEX section_section_label IF NOT EXISTS
FOR (n:Section)
ON (n.section_label);

CREATE INDEX section_effective_start IF NOT EXISTS
FOR (n:Section)
ON (n.effective_start_date);

CREATE INDEX concept_canonical_name IF NOT EXISTS
FOR (n:Concept)
ON (n.canonical_name);

CREATE INDEX rateband_source_doc_id IF NOT EXISTS
FOR (n:RateBand)
ON (n.source_doc_id);

CREATE INDEX rateband_effective_start IF NOT EXISTS
FOR (n:RateBand)
ON (n.effective_start_date);

CREATE INDEX proceduremilestone_source_doc_id IF NOT EXISTS
FOR (n:ProcedureMilestone)
ON (n.source_doc_id);

CREATE INDEX proceduremilestone_kind IF NOT EXISTS
FOR (n:ProcedureMilestone)
ON (n.milestone_kind);

CREATE INDEX irdhubsummary_topic IF NOT EXISTS
FOR (n:IrdHubSummary)
ON (n.topic_label);
