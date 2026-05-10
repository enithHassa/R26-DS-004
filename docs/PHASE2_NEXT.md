# Phase 2 readiness (after Phase 1b)

Phase 2 in the roadmap is **model zoo + comparison on law-grounded benchmarks** (NLU / embeddings / optional SLM), with **mandatory `chunk_id` citations**.

## Inputs you should have from Phase 1b

- `data/processed/ird/corpus_v1.jsonl` (and optional `corpus_v1.sqlite`)
- Filled `data/raw/ird/` manifest with Tier A sources, hashes, and dates
- `data/processed/ird/extraction_qa_report.md` from manual + automated QA

## Next implementation steps (suggested order)

1. Replace placeholders in `evaluation/benchmark_seed_template.jsonl` with real `gold_chunk_ids` from your corpus.
2. Freeze a **benchmark split** (train/dev/test) and record it in `evaluation/experiment_run_template.json` per run.
3. Add NLU dataset loaders under `nlu/` and a training/eval CLI or notebook under `models/language-model/`.
4. Run baseline models (encoder NLU + embedding model) and log metrics + **grounding adherence** (predictions must align with gold chunks).
5. Wire the winning inference schema toward `backend/comp-language-model` API routes (Phase 2 deliverable: NLU service stub).

## Definition of done for Phase 2 gate (from roadmap)

- Model comparison report with latency/cost and chunk-grounding checks
- Frozen winner IDs + inference JSON schema
- Seed benchmark with expert-reviewed subset optional but recommended
