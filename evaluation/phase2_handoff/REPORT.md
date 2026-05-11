# Phase 2 handoff report

Single-file summary for supervisors, examiners, or repo handoff. Regenerate after new runs or gate changes.

**Generated (UTC):** 2026-05-10T07:37:46Z

## M5 frozen baseline

```json
{
  "gate_id": "M5_phase2_2026_05_11",
  "status": "accepted",
  "baseline_name": "tfidf_corpus_v1_plus_centroid_intent",
  "summary": "Phase 2 production baseline until a new model is promoted through experiment logs and this gate is revised.",
  "component": "language-model",
  "component_version": "0.1.0",
  "corpus_version": "corpus_v1",
  "retrieval": {
    "implementation": "backend/comp-language-model/app/services/tfidf_chunk_index.py",
    "eval": "scripts/phase2_eval_retrieval_tfidf.py"
  },
  "intent": {
    "implementation": "backend/comp-language-model/app/services/intent_tfidf_centroid.py",
    "training_data": "COMP_LLM_INTENT_BENCHMARK_JSONL (intent_classification + joint_nlu_retrieval rows)",
    "eval": "scripts/phase2_eval_intent_tfidf.py"
  },
  "joint_metric": {
    "eval": "scripts/phase2_eval_joint_tfidf.py",
    "definition": "intent_pred == gold_intent AND any gold_chunk_id in top-k"
  },
  "api": {
    "service_path": "POST /api/v1/nlu/parse",
    "gateway_path": "POST /api/v1/llm/nlu/parse",
    "frozen_request_schema": "evaluation/frozen/nlu_parse_request.schema.json",
    "frozen_response_schema": "evaluation/frozen/nlu_parse_response.schema.json"
  },
  "experiment_log": {
    "bundle": "scripts/phase2_experiment_run.py",
    "default_append_path": "evaluation/phase2_runs.jsonl",
    "leaderboard": "scripts/phase2_leaderboard.py",
    "handoff_report": "scripts/phase2_export_handoff.py",
    "handoff_default_out": "evaluation/phase2_handoff/REPORT.md"
  },
  "regression": {
    "smoke_script": "scripts/phase2_regression_smoke.py",
    "fixtures": "evaluation/fixtures/phase2_smoke/",
    "ci_workflow": ".github/workflows/phase2-smoke.yml"
  },
  "frozen_supporting": {
    "task_registry": "evaluation/phase2_task_registry.json",
    "experiment_run_template": "evaluation/experiment_run_template.json"
  },
  "environment": {
    "COMP_LLM_CORPUS_JSONL": "Set to corpus_v1.jsonl for retrieval (model=tfidf-baseline, corpus_loaded=true).",
    "COMP_LLM_INTENT_BENCHMARK_JSONL": "Optional; when set, intent_model=tfidf-centroid and predicted_intent populated.",
    "COMP_LLM_RETRIEVAL_TOP_K": "Default top-k when request omits top_k (default 8)."
  },
  "promotion_rule": "A new encoder or retriever replaces this baseline only after: (1) runs appended to phase2_runs.jsonl show improvement on agreed metrics, (2) frozen schemas updated or versioned, (3) this file superseded with a new gate_id and superseded_by link.",
  "superseded_by": null
}
```

## Task registry

- **registry_version:** 1.0
- **task count:** 4
- **path:** `evaluation/phase2_task_registry.json`

| task_id | name |
|---|---|
| retrieval_law_grounding | Law-grounded passage retrieval |
| intent_classification | Tax intent classification |
| joint_nlu_retrieval | Joint intent + law-grounded retrieval |
| answer_citation_grounding | Generated answer with citation grounding |

## Leaderboard (`phase2_runs.jsonl`)

_No experiment log at this path yet. Append runs with `scripts/phase2_experiment_run.py` (Step 5)._

## Frozen NLU schemas

- `evaluation/frozen/nlu_parse_request.schema.json`
- `evaluation/frozen/nlu_parse_response.schema.json`

## Copy-paste commands

```text
# Regression smoke (Step 7)
python scripts/phase2_regression_smoke.py

# Experiment bundle dry-run (replace paths)
python scripts/phase2_experiment_run.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --benchmark evaluation/benchmark_seed_template.jsonl --dry-run

# Leaderboard
python scripts/phase2_leaderboard.py --input evaluation/phase2_runs.jsonl
```

---

*Produced by `scripts/phase2_export_handoff.py` (Phase 2 Step 8).*
