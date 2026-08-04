# Adaptive Tax — Phase 4 evaluation

Dissertation **Chapter 4** metrics for Component 5 (Adaptive Tax). Scorers are offline-friendly (fixture extract/explain). Live OpenAI responses can be saved as JSON and scored with the same scripts.

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
  fixtures/
  viva_recording_checklist.md
  runs/
```

## Reproduce each metric

### 1. Extraction precision

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/extraction/score_extraction.py
# optional: --predicted path\to\live_extract.json
```

Gold: `extraction/labeled_sample_20fields.json` (20 fields from Act 02/2025 Sec 52).  
Default predicted: `models/adaptive-tax/fixtures/section52_extract_sample.json`.

### 2. Calculation accuracy

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

Record outcome in `calculation/RESULTS.md`. Target: **8/8** named examples (`ex01`–`ex08`).

### 3. Citation faithfulness

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/citation_faithfulness/score_citations.py `
  --input models/adaptive-tax/fixtures/explain_ex04_sample.json
```

Checks `set(sections_cited) ⊆ set(sections_retrieved)`.

### 4. Explanation grounding

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/explanation_grounding/score_grounding.py `
  --input evaluation/adaptive-tax/fixtures/explain_grounding_cases.jsonl
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/explanation_grounding/score_grounding.py `
  --input models/adaptive-tax/fixtures/explain_ex04_sample.json
```

Each narrative sentence must map to a step with `evidence_chunk_ids` and/or `rule_source_id` (fixture mode attaches ids explicitly).

### 5. Amendment adaptivity

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
```

Also: `scripts/adaptive_tax_phase4_demo.py` (HTTP). Protocol: `amendment_adaptivity/ex08_and_demo_protocol.md`.

## Filled Chapter 4 table

See [`metrics_table.md`](metrics_table.md).

## Experiment run template

Copy [`experiment_run_template.json`](experiment_run_template.json) (mirrors Comp 4 `evaluation/experiment_run_template.json`) and fill metric fields after a run.

## Viva recording (Step 8)

Checklist: [`viva_recording_checklist.md`](viva_recording_checklist.md).  
Commands: runbook **Adaptive Tax Phase 4 — Viva recording checklist**.

### Recording path

> Video files stay **outside** git (external drive / `~/Videos` / OneDrive). Paste the absolute path here after you record.

| Field | Value |
|-------|--------|
| Recorded at (local date) | _TBD_ |
| Operator | _TBD_ |
| Explain mode shown | fixture / openai / both |
| Absolute path to recording | _e.g. `D:\Viva\adaptive-tax-phase4-YYYY-MM-DD.mp4`_ |
| Duration (approx.) | _TBD_ |
| Notes | _T1/T2 amounts, Neo4j up?, Chroma hits?_ |
