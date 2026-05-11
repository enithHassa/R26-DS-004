# Knowledge Graph Workspace

Graph schemas, build scripts, and exported snapshots for Tax Knowledge Graph work.

## Phase 3 ontology (Steps 1–2)

- **`ontology_v1.json`** (v**1.2.0**) — **Node labels** (Step 1 + Step 10 **ConsolidatedViewPassage**) plus **relationship types** (Step 2 + Step 10 **VIEW_**\*): `PART_OF`, `HAS_CHUNK`, …, `COVERS_RELIEF`, `VIEW_IN_INSTRUMENT`, `VIEW_TRACES_TO_SECTION`, `VIEW_TRACES_TO_INSTRUMENT`, each with `from_labels` / `to_labels` and optional `lex_specialis_relevant`. Shared optional edge properties are under `optional_edge_properties`.
- **`scripts/kg_ontology_lib.py`** — `load_ontology()`, `validate_ontology()` for CI and ETL.

## Phase 3 Step 3 — Chunk metadata for KG loading

- **`chunk_metadata_kg_v1.json`** — Required / recommended fields and mapping for `effective_from` + `section_label`.
- **`ird_corpus_lib.py`** — `normalize_chunk_for_kg()`, `validate_kg_chunk_metadata()`, `primary_section_label()`.
- **`scripts/validate_corpus_kg_metadata.py`** — CLI over a JSONL file; use `--strict-doc-meta` for production Tier A/B rows (non-empty `tier`, `instrument_type`).

## Phase 3 Step 4 — ETL (chunk → graph pilot)

- **`etl_chunk_to_graph_v1.json`** — MERGE order, `section_uid` formula, property mappings, which relationship types this pilot emits (`HAS_CHUNK`, `PART_OF`).
- **`scripts/kg_etl_lib.py`** — `make_section_uid()`, `etl_bundle_from_chunk_row()`, `assert_bundle_has_text_chunk()`.
- **`scripts/export_kg_etl_preview.py`** — print JSON bundles for the first `--limit` valid rows (runs KG metadata validation first).

## Phase 3 Step 5 — Neo4j constraints and indexes

- **`neo4j/00_constraints.cypher`** — unique keys for all eight node labels (`chunk_id`, `section_uid`, `source_doc_id`, …).
- **`neo4j/01_range_indexes.cypher`** — range indexes for `tier`, `source_doc_id`, effective dates, `content_kind`, etc.
- **`neo4j/README.md`** — `cypher-shell` and Python apply instructions.
- **`requirements-neo4j.txt`** — optional `neo4j` driver for `scripts/neo4j_apply_schema.py`.

## Phase 3 Step 6 — Load nodes (Neo4j pilot)

- **`scripts/neo4j_load_corpus_chunks.py`** — per JSONL row: MERGE **LawInstrument** → **Section** (if any) → **TextChunk**, then **PART_OF** / **HAS_CHUNK** (one transaction per row). Options: `--dry-run`, `--no-text`, `--strict-doc-meta`, `--limit`.
- **`kg_etl_lib.bundle_nodes_merge_order()`** — sorts bundle nodes into instrument → section → chunk order before MERGE.

## Phase 3 Step 7 — Curated / automated edges

- **`edge_ingest_v1.json`** — JSONL row shape; optional `confidence`, `review_status`, `source_note`, etc. (ontology `optional_edge_properties` only).
- **`kg_curated_edges_lib.py`** — `validate_edge_row()`, `edge_properties_for_neo4j()`.
- **`neo4j_load_curated_edges.py`** — ingest validated JSONL; `--dry-run`, `--warn-miss` when endpoints are absent.
- **`kg_edges_heuristic_lib.py`** + **`export_heuristic_mentions_edges.py`** — weak **MENTIONS** (TextChunk → Concept) from alias substring matches; set `review_status` to `auto_alias_match`.
- **`examples/concepts_seed.json`**, **`examples/curated_edges_sample.jsonl`** — small references (ensure nodes exist before loading sample edges).

## Phase 3 Step 8 — Lex Specialis metadata

- **`lex_specialis_v1.json`** — authority classes, default weights / `specificity_rank`, `precedence_order`, Section bonus.
- **`kg_lex_specialis_lib.py`** — `infer_authority_class()`, `lex_fields_for()`, `authority_precedence_index()`.
- **`kg_etl_lib` ETL bundles v1.1.0** — LawInstrument, Section, TextChunk nodes include `authority_class`, `authority_weight_numeric`, `specificity_rank`, `lex_effective_from`, `lex_effective_to`.
- **`neo4j/02_lex_indexes.cypher`** — applied by `neo4j_apply_schema.py` after `01_range_indexes.cypher`.

## Phase 3 Step 9 — Override paths (OVERRIDES / MODIFIES / SUPERSEDES)

- **`lex_override_paths_v1.json`** — chosen strategy: **typed relationships** + Step 8 node metadata; semantics for each rel; Phase 4 query hints.
- **`kg_override_edges_lib.py`** — optional **strict** checks for override rows (`source_note`, `review_status`).
- **`neo4j_load_curated_edges.py --strict-lex-overrides`** — enforce provenance on OVERRIDES/MODIFIES/SUPERSEDES.
- **`examples/override_edges_sample.jsonl`** — illustration only (fix `source_doc_id` / `section_uid` to your corpus).

## Phase 3 Step 10 — Consolidated-text view (optional)

- **`consolidated_view_v1.json`** — why **ConsolidatedViewPassage** exists and how it links to real sources.
- **Ontology 1.2.0** — node **ConsolidatedViewPassage**; rels **VIEW_IN_INSTRUMENT**, **VIEW_TRACES_TO_SECTION**, **VIEW_TRACES_TO_INSTRUMENT**.
- **`kg_consolidated_view_lib.py`** — `make_anchor_id()`, `validate_anchor_row()`, `props_for_neo4j()`.
- **`neo4j_load_consolidated_anchors.py`** — MERGE anchors; trace edges via **`neo4j_load_curated_edges.py`**.
- **`neo4j/03_consolidated_view_indexes.cypher`** + extra row in **`00_constraints.cypher`** (applied by `neo4j_apply_schema.py`).
- **`examples/consolidated_view_anchor_rows.jsonl`**, **`examples/consolidated_view_trace_edges_sample.jsonl`**.

## Phase 3 Step 11 — NLU entity → graph mapping

- **`nlu_entity_graph_map_v1.json`** — per **`nlu_entity_type`**: **`target_node_label`**, **`match`** strategy, **`fallback_behavior`**, user-facing hints.
- **`kg_nlu_entity_map_lib.py`** — `load_entity_map()`, `validate_entity_map()`, `entity_row_for_type()`.

## Phase 3 Step 12 — NLU intent → graph entry

- **`nlu_intent_graph_map_v1.json`** — per **`nlu_intent`**: parameterized **`cypher_template`**, **`entry.strategy`**, **`fallback_behavior`**, **`expansion_hints`** (documentation).
- **`kg_nlu_intent_map_lib.py`** — `load_intent_map()`, `validate_intent_map()`, `intent_row_for_intent()` (falls back to **`_default`**).

## Phase 3 Step 13 — Node-linked embedding bundles

- **`node_embeddings_v1.json`** — artifact contract: **`node_embeddings_meta.json`** + **`.npz`** beside it (vectors stored **outside** Neo4j by default); join key **`neo4j_label`** + **`id_property`** + id array aligned with **`embeddings`**.
- **`scripts/kg_node_embeddings_lib.py`** — `validate_meta()`, `write_bundle()`, `load_bundle()`, `write_pending_meta()` (dry-run manifest).
- **`scripts/compute_node_embeddings_bundle.py`** — from corpus JSONL via **`DenseChunkIndex.from_jsonl`**; **`--dry-run`** counts lines only. Full encode needs **`backend/requirements-retrieval-dense.txt`**; set **`PYTHONPATH`** to include **`backend/comp-language-model`** (see **`docs/PHASES_RUNBOOK.md`** Step 13).

## Phase 3 Step 14 — Serve bundles from the language-model API

- **`COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR`** — with **`COMP_LLM_RETRIEVAL_BACKEND=dense`**, load **`node_embeddings_meta.json`** + NPZ via **`DenseChunkIndex.from_embedding_bundle_dir`** ( **`app/services/node_embedding_bundle.py`** wraps **`scripts/kg_node_embeddings_lib.load_bundle`**). Keep **`COMP_LLM_CORPUS_JSONL`** for chunk text used in citations.

## Phase 3 Step 15 — API retrieval rows carry graph join keys

- **`app/services/corpus_chunk_kg_join.py`** — scans corpus JSONL and builds **`chunk_id` → `{source_doc_id, section_uid, …}`** using **`ird_corpus_lib.normalize_chunk_for_kg`** + **`kg_etl_lib.make_section_uid`**, so NLU hits and query citations match Neo4j pilot keys without a round trip.
