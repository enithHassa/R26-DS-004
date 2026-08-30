# Adaptive Tax — Phase 4 / Phase 5 evaluation

Dissertation **Chapter 4** metrics for Component 5 (Adaptive Tax). Scorers are offline-friendly (fixture extract/explain). Live OpenAI responses can be saved as JSON and scored with the same scripts.

**Phase 6.9 one-shot (recommended — extends 5.9):**

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/run_chapter4_metrics.py --write-metrics-md
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/generate_figures.py
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase6_demo.py
```

**Phase 5.9 one-shot (calculator track only):**

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase5/run_chapter4_metrics.py --write-metrics-md
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_demo.py
```

## Layout

```
evaluation/adaptive-tax/
  README.md
  metrics_table.md
  experiment_run_template.json
  extraction/
  calculation/
  citation_faithfulness/
  explanation_grounding/
  amendment_adaptivity/
  coverage/
  provenance/
  phase5/
  phase6/
  rag/
  fixtures/
  viva_recording_checklist.md
  runs/
  rag_gold_queries_v1.jsonl
```

Phase 6.9 details: [`phase6/README.md`](phase6/README.md).

### RAG gold Precision@3 / Recall@3 (Phase 8)

Human gold: [`rag_gold_queries_v1.jsonl`](rag_gold_queries_v1.jsonl). Automated scorer (no GPT):

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
# After section-aware Chroma rebuild
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_rag_gold_eval.py `
  --label after --k 3 --min-score 0.55 --sweep-min-scores 0.45,0.50,0.55,0.60 --merge-md

# Optional baseline on archived pre-section-aware corpus
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_rag_gold_eval.py `
  --label before `
  --corpus-jsonl data/processed/adaptive-tax/corpus_v1.pre_section_aware.jsonl `
  --persist-dir data/processed/adaptive-tax/chroma_baseline_pre_section `
  --reset --k 3 --min-score 0.55 --merge-md
```

Report: [`rag/RESULTS.md`](rag/RESULTS.md). `RAG_MIN_SCORE` is a retrieval noise floor only — not legal confidence.

### RAG legal coverage report (Phase 9)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_rag_coverage_report.py
```

Outputs: [`rag/rag_legal_coverage.md`](rag/rag_legal_coverage.md) + [`rag/rag_legal_coverage.json`](rag/rag_legal_coverage.json) (before/after tagging, per-section operative+YA, citation PASS/FAIL, gold P@3/R@3, deterministic vs GPT-assisted counts, chosen `RAG_MIN_SCORE`).

## Reproduce each metric

### 1. Coverage

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/coverage/score_coverage.py
```

### 2. Extraction precision

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/extraction/score_extraction.py
# Per harvested section (Phase 5.9):
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/extraction/score_harvest_sections.py
```

Gold (Sec 52 labeled): `extraction/labeled_sample_20fields.json`.  
Harvest fixtures: `models/adaptive-tax/fixtures/*_harvest_v1.json`.

### 3. Calculation accuracy

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

Record outcome in `calculation/RESULTS.md`. Target: all named goldens for covered areas pass (`ex01`–`ex08` + `ex09`–`ex17`).

### 4. Provenance completeness

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/provenance/score_provenance.py
```

Target: **1.00** on covered executable steps.

### 5. Citation faithfulness

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/citation_faithfulness/score_citations.py `
  --input models/adaptive-tax/fixtures/explain_ex04_sample.json
```

Checks `set(sections_cited) ⊆ set(sections_retrieved)`. Target: **1.00**.

### 6. Explanation grounding

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/explanation_grounding/score_grounding.py `
  --input evaluation/adaptive-tax/fixtures/explain_grounding_cases.jsonl
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/explanation_grounding/score_grounding.py `
  --input models/adaptive-tax/fixtures/explain_ex04_sample.json
```

Each narrative sentence must map to a step with `evidence_chunk_ids` and/or `rule_source_id`. Target: **1.00**.

### 7. Amendment adaptivity

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_demo.py
# Live API (optional):
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_demo.py --http
```

Protocol: `amendment_adaptivity/ex08_and_demo_protocol.md`.

## Filled Chapter 4 table

See [`metrics_table.md`](metrics_table.md).

## Experiment run template

Copy [`experiment_run_template.json`](experiment_run_template.json) (or use `phase5/run_chapter4_metrics.py` which writes `runs/phase5_9_*.json`).

## Viva recording (Phase 6.9)

Checklist: [`viva_figure_checklist.md`](phase6/viva_figure_checklist.md) (figures) + [`viva_recording_checklist.md`](viva_recording_checklist.md) (dual-YA demo).  
Demo: `scripts/adaptive_tax_phase6_demo.py` (offline) or Phase 5 `--http` with API on `:8005`.

### Recording path

> Video files stay **outside** git (external drive / `~/Videos` / OneDrive). Paste the absolute path here after you record.

| Field | Value |
|-------|--------|
| Recorded at (local date) | _TBD_ |
| Operator | _TBD_ |
| Explain mode shown | fixture / openai / both |
| Absolute path to recording | _e.g. `D:\Viva\adaptive-tax-phase5-YYYY-MM-DD.mp4`_ |
| Duration (approx.) | _TBD_ |
| Notes | _T1/T2 amounts, Sec 52 quotes, Coverage 8/8, Neo4j optional_ |
