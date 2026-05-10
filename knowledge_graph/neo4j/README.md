# Neo4j schema (Phase 3 Step 5)

Requires **Neo4j 5.x** (Aura, Desktop, or Docker) for `CREATE CONSTRAINT ... REQUIRE ... IS UNIQUE` syntax.

## Files

| File | Purpose |
|------|---------|
| `00_constraints.cypher` | One **unique** constraint per node kind (`ontology_v1.json` `id_property`). |
| `01_range_indexes.cypher` | **Range** indexes on `tier`, `source_doc_id`, dates, and other filter fields. |
| `02_lex_indexes.cypher` | Phase 3 Step 8 — **Lex Specialis** lookups (`authority_class`, `specificity_rank`, `lex_effective_from`). |
| `03_consolidated_view_indexes.cypher` | Phase 3 Step 10 — **ConsolidatedViewPassage** (`source_doc_id`, `consolidated_as_of`, `chunk_id`). |

## Apply with cypher-shell

```powershell
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<password>"
cypher-shell -a neo4j://127.0.0.1:7687 -u $env:NEO4J_USER -p $env:NEO4J_PASSWORD -f 00_constraints.cypher
cypher-shell -a neo4j://127.0.0.1:7687 -u $env:NEO4J_USER -p $env:NEO4J_PASSWORD -f 01_range_indexes.cypher
```

Paths: run from this directory or pass absolute paths to `-f`.

## Load corpus chunks (Phase 3 Step 6)

After constraints/indexes are applied, ingest JSONL (pilot: LawInstrument, Section, TextChunk + `PART_OF` / `HAS_CHUNK`):

```powershell
Set-Location ..\..
py -3 scripts/neo4j_load_corpus_chunks.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --dry-run --limit 5
```

See `docs/PHASES_RUNBOOK.md` for env vars and flags (`--strict-doc-meta`, `--no-text`).

## Apply with Python

```powershell
pip install -r knowledge_graph/requirements-neo4j.txt
$env:NEO4J_URI = "neo4j://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<password>"
py -3 scripts/neo4j_apply_schema.py
```

## Neo4j 4.4

Older servers use `CREATE CONSTRAINT ON (n:Label) ASSERT n.prop IS UNIQUE`. Upgrade or translate statements manually if you are pinned to 4.4.
