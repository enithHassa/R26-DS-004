# Intelligent Tax Advisory Language Model - Phase 1 Architecture

This document defines the Phase 1 foundation for Component 4 of `R26-DS-004`.
It aligns repository layout, source governance, and service contracts before
Phase 1b corpus ingestion and Phase 2 model comparison.

## Scope

- Establish additive repository structure without breaking existing components.
- Define source-governance inputs for IRD corpus ingestion.
- Define experiment-run metadata requirements.
- Define answer traceability contract to support legal evidence output.

## Repository Layout (Phase 1 baseline)

- `data/raw/ird/`: immutable IRD downloads, source manifest, checksums.
- `data/processed/`: extracted text, chunks, and normalized corpus exports.
- `models/language-model/`: model configs, checkpoints, and experiment outputs.
- `nlu/`: intent/entity datasets, label guides, and evaluation artifacts.
- `knowledge_graph/`: graph build specs and exported snapshots.
- `retrieval/`: retrieval strategies and evaluation harnesses.
- `reasoning/`: symbolic rules and validation logic.
- `api/`: API-level specs and integration contracts.
- `ui/`: UI-level requirements and proof-map display notes.
- `evaluation/`: benchmark definitions and metrics reports.

## Service Baseline

The language-model backend skeleton is implemented in
`backend/comp-language-model/app/` with:

- `GET /health` for liveness.
- `GET /ready` for startup readiness checks.

These endpoints are intentionally minimal and provide a stable integration
surface for API Gateway wiring in later phases.

## Source Governance Standards

Source-governance artifacts live under `data/raw/ird/`:

- `source_manifest_template.csv`: canonical row schema for every source.
- `README.md`: ingestion and versioning workflow.

Minimum manifest fields for each source:

- `source_doc_id` (stable internal identifier)
- `source_url` (exact download/source URL)
- `title` and `doc_type`
- `tier` (`A`, `B`, `C`)
- `publication_date`, `effective_start_date`, `effective_end_date`
- `version_label` and `supersedes_source_doc_id`
- `sha256` and `ingested_at_utc`
- `authority_weight` and `is_draft`

## Experiment Tracking Standard

Each training/evaluation run must record:

- `run_id`
- `component_version` and `model_version`
- `corpus_version`
- `rule_engine_version`
- dataset split identifiers
- metrics and runtime/cost metadata

Run metadata is standardized in `evaluation/experiment_run_template.json`.

## Phase 1b corpus pipeline (reference)

- `scripts/ird_phase1b_bootstrap.py`: IRD link inventory, optional download + manifest autofill.
- `scripts/extract_ir_pdf_text.py`: PDF text + **corpus_v1** JSONL, optional pdfplumber tables, optional PDF outline breadcrumbs.
- `scripts/ird_extract_html.py`: HTML / ASPX summaries to **corpus_v1** JSONL.
- `scripts/ird_manifest_build_corpus.py`: batch build from a filled manifest CSV.
- `scripts/ird_extraction_qa_report.py`: markdown QA summary for spot-checks (Day 4+).
- `scripts/ird_corpus_sqlite.py`: load JSONL into **SQLite** (`corpus_v1.sqlite`) for querying.
- `scripts/ird_phase1b_finalize.py`: validate manifest, run build + QA + SQLite ingest.
- `scripts/ird_pdf_outline.py`: PDF bookmark flattening + per-page breadcrumb trail.
- `scripts/ird_corpus_lib.py`: shared chunk IDs, metadata fields, and JSONL records.

Phase 2 entry notes: `docs/PHASE2_NEXT.md`. Benchmark placeholder: `evaluation/benchmark_seed_template.jsonl`.

## Traceability and Evidence Contract

Every generated answer must include:

- `answer_text`
- `evidence` list with `chunk_id` and `source_doc_id`
- `traceability` object with run/corpus/rule versions

This contract is defined in `backend/shared/schemas/traceability.py` and is
intended for adoption by Component 4 API endpoints in Phase 2 onward.
