// Phase 3 Step 10 — indexes for consolidated view anchors

CREATE INDEX consolidatedviewpassage_source_doc IF NOT EXISTS
FOR (n:ConsolidatedViewPassage)
ON (n.source_doc_id);

CREATE INDEX consolidatedviewpassage_as_of IF NOT EXISTS
FOR (n:ConsolidatedViewPassage)
ON (n.consolidated_as_of);

CREATE INDEX consolidatedviewpassage_chunk_id IF NOT EXISTS
FOR (n:ConsolidatedViewPassage)
ON (n.chunk_id);
