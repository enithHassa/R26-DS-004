// Phase 3 Step 8 — indexes for Lex Specialis filters (Neo4j 5+)

CREATE INDEX lawinstrument_authority_class IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.authority_class);

CREATE INDEX lawinstrument_specificity_rank IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.specificity_rank);

CREATE INDEX section_authority_class IF NOT EXISTS
FOR (n:Section)
ON (n.authority_class);

CREATE INDEX section_specificity_rank IF NOT EXISTS
FOR (n:Section)
ON (n.specificity_rank);

CREATE INDEX textchunk_authority_class IF NOT EXISTS
FOR (n:TextChunk)
ON (n.authority_class);

CREATE INDEX textchunk_specificity_rank IF NOT EXISTS
FOR (n:TextChunk)
ON (n.specificity_rank);

CREATE INDEX lawinstrument_lex_effective_from IF NOT EXISTS
FOR (n:LawInstrument)
ON (n.lex_effective_from);

CREATE INDEX textchunk_lex_effective_from IF NOT EXISTS
FOR (n:TextChunk)
ON (n.lex_effective_from);
