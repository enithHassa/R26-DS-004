# Phase 2 plan — Model zoo & law-grounded benchmarks (Component 4)

## Step 1 — Decide what you are testing (tasks)

**Phase 2 (roadmap): Model zoo, training, and comparative evaluation (weeks 4–8)** starts by freezing **evaluation tasks**, not models.

- **Canonical registry:** [`evaluation/phase2_task_registry.json`](../evaluation/phase2_task_registry.json) — machine- and human-readable `task_id` definitions, gold fields, primary metrics, and per-task validation rules.
- **Benchmark rows** must set `task_id` (or inherit the default `retrieval_law_grounding` from the registry). Optional `intent` / `gold_intent` rules are documented per task.
- **Validation:** `scripts/validate_benchmark_corpus.py` checks task shape **and** that `gold_chunk_ids` exist in your `corpus_v1.jsonl` (use `--skip-task-shape` for corpus-only checks).
- **Retrieval eval:** `scripts/phase2_eval_retrieval_tfidf.py` scores only **retrieval** tasks (`retrieval_law_grounding`, `joint_nlu_retrieval`); intent-only rows are skipped for retrieval metrics.

## Step 2 — First NLU baseline (intent classification)

Pick a **simple, reproducible** intent model before sentence-transformers or fine-tuned encoders.

- **Baseline:** TF-IDF bag-of-words + **per-label centroid** (L2-normalized); prediction = argmax cosine similarity to centroids (`scripts/phase2_intent_tfidf.py`).
- **Eval CLI:** `scripts/phase2_eval_intent_tfidf.py` on all benchmark rows with `task_id` ∈ {`intent_classification`, `joint_nlu_retrieval`} and a resolvable gold intent (`gold_intent` or `intent`).
- **Modes:** **LOOCV** (default, needs ≥2 intent rows) or **holdout** (`--mode holdout --test-fraction 0.25 --seed 42`).
- **Metrics:** exact-match **accuracy** and **macro F1** (sklearn, `zero_division=0`).
- **Next:** richer intent features; offline metrics still use Step 2 LOOCV / Step 3 joint (API fits on full benchmark — Step 4).

## Step 3 — Joint pipeline metric (intent ∧ retrieval)

Measure **end-to-end routing + grounding** on `task_id` = **`joint_nlu_retrieval`** rows.

- **Definition:** `joint_success` = (**predicted intent** = gold intent) **and** (≥1 **gold_chunk_id** appears in **top-k** TF-IDF chunks). Same intent baseline as Step 2; same retrieval index as `phase2_eval_retrieval_tfidf.py`.
- **CLI:** `scripts/phase2_eval_joint_tfidf.py --corpus-jsonl … --benchmark … [--mode loocv|holdout] [--per-example]`
- **Training pool for intent:** all rows with `intent_classification` or `joint_nlu_retrieval` and a gold label; LOOCV excludes the current joint row by `example_id`.
- **Next:** swap dense retrieval into the joint script; compare with API `predicted_intent` (Step 4).

## Step 4 — API: intent + retrieval on `POST /api/v1/nlu/parse`

Wire the **same TF-IDF centroid intent** as Step 2 into the language-model service.

- **Env:** `COMP_LLM_INTENT_BENCHMARK_JSONL` → benchmark JSONL (same row filter as Step 2: `intent_classification` + `joint_nlu_retrieval` with `gold_intent` / `intent`). Fits **one** classifier at startup on **all** qualifying rows (train on full file; for unbiased offline metrics use Step 2 LOOCV / Step 3 joint).
- **Response fields:** `predicted_intent`, `intent_model` (`tfidf-centroid` when loaded). `intent` remains the echo of optional request `intent_hint` (upstream routing).
- **Code:** `app/services/intent_benchmark.py`, `app/services/intent_tfidf_centroid.py`, lifespan in `app/main.py`.
- **Next:** dense encoders, `/query` with citations, or hot-reload benchmark path in dev.

## Step 5 — Experiment tracking (bundle + JSONL log)

Reproducible **model zoo** comparisons need one artifact per run.

- **CLI:** `scripts/phase2_experiment_run.py` — runs retrieval, intent, and joint TF-IDF evals (subprocess), merges JSON into one record (aligned with `evaluation/experiment_run_template.json`, plus `phase2_eval_outputs` and optional `phase2_errors`).
- **Output:** appends one line to `evaluation/phase2_runs.jsonl` by default (`--dry-run` prints only). Set `--model-version` for candidate id; use `--skip-retrieval`, `--skip-intent`, or `--skip-joint` when a sub-eval does not apply.
- **Template:** `evaluation/experiment_run_template.json` lists top-level fields; Phase 2 fills `metrics.phase2_*` and nested raw eval JSON.
- **M5:** completed — see `evaluation/frozen/phase2_M5_baseline.json` and runbook **Phase 2 M5**. Optional: CI job running `phase2_experiment_run.py --dry-run` on a tiny fixture.

## Step 6 — Report & leaderboard (workstream 6)

Turn **`phase2_runs.jsonl`** into a comparable **leaderboard** for theses, stand-ups, and promotion decisions.

- **CLI:** `scripts/phase2_leaderboard.py` — reads `evaluation/phase2_runs.jsonl` (override with `--input`), outputs **Markdown** (default), **JSON**, or **CSV**.
- **Sort:** `--sort joint` (default), `retrieval`, `intent` (macro F1), or `latency` (shortest `duration_seconds` first). Runs with `phase2_errors` are **skipped** unless `--include-errors`.
- **Columns:** model_version, retrieval R@k, n_evaluated, intent accuracy / macro-F1, joint success rate, joint n, wall duration, `cost.estimated_total`, error flag, run_id.
- **Next:** Step 7–8 (CI smoke + handoff `REPORT.md`).

## Step 7 — Regression & CI smoke (handoff)

Keep Phase 2 from **silently breaking** when eval scripts or the task registry change.

- **Fixtures (committed):** `evaluation/fixtures/phase2_smoke/corpus_v1.jsonl` + `benchmark.jsonl` — tiny corpus and three rows (retrieval / joint / intent) valid against `phase2_task_registry.json`.
- **CLI:** `scripts/phase2_regression_smoke.py` — runs `validate_benchmark_corpus.py` on fixtures, then `phase2_experiment_run.py --dry-run`, asserts no `phase2_errors` and required metric keys.
- **CI:** `.github/workflows/phase2-smoke.yml` runs the regression script on push/PR when Phase 2 paths change.
- **Next:** Step 8 handoff export for thesis / examiner packs.

## Step 8 — Handoff report (single Markdown bundle)

One command assembles **M5 baseline JSON**, **task registry** table, **leaderboard** (from `phase2_runs.jsonl` if present), frozen schema paths, and copy-paste commands into a single file for supervisors or documentation.

- **CLI:** `scripts/phase2_export_handoff.py` — default output `evaluation/phase2_handoff/REPORT.md`; use `--stdout` for pipes, `--runs PATH` / `--out PATH` to override.
- **Next:** Step 9 benchmark splits for held-out evaluation.

## Step 9 — Benchmark train / dev / test splits

Fair **model zoo** comparisons require held-out examples. This step materializes three JSONL files from one benchmark.

- **CLI:** `scripts/phase2_split_benchmark.py --benchmark PATH --out-dir DIR --strategy explicit|hash`
- **`explicit`:** each row must include **`split`**: `train`, `dev`, or `test` (aliases: `val`, `validation` → `dev`). Fails if any row is missing or invalid.
- **`hash`:** deterministic assignment from **`example_id`** + `--seed` (SHA-256); use `--train-fraction` / `--dev-fraction` (test is the remainder). Every output row gets a normalized `split` field.
- **Outputs:** `{prefix}_train.jsonl`, `{prefix}_dev.jsonl`, `{prefix}_test.jsonl` (default prefix `benchmark`).
- **Next:** Step 10 held-out eval (below); then dense retrieval (M3).

## Step 10 — Split-aware eval (train fit / eval score)

Use **Step 9** outputs so the intent centroid is fit only on **train** rows, while metrics are computed on a separate **eval** JSONL (e.g. merged `dev`+`test`).

- **Intent:** `scripts/phase2_eval_intent_tfidf.py --train-benchmark PATH_TRAIN --benchmark PATH_EVAL` — output `mode`: `held_out_train_split`.
- **Joint:** `scripts/phase2_eval_joint_tfidf.py --intent-train-benchmark PATH_TRAIN --corpus-jsonl … --benchmark PATH_EVAL` — same `mode` when using the train file.
- **Bundle:** `scripts/phase2_experiment_run.py --train-benchmark PATH_TRAIN --benchmark PATH_EVAL` — retrieval stays on **eval** only; intent and joint use the held-out path. Record `dataset.split` = `held_out_train_eval`, plus `train_benchmark_path` / `train_sample_count`.

## Step 11 — Dense retrieval baseline (sentence-transformers)

Same **recall@k any gold** metric and task filters as TF-IDF, with an embedding index over `corpus_v1.jsonl`.

- **Index:** `backend/comp-language-model/app/services/dense_chunk_index.py` — `DenseChunkIndex.from_jsonl` (normalized embeddings, cosine top-k).
- **Eval:** `scripts/phase2_eval_retrieval_dense.py` — CLI mirrors TF-IDF eval; JSON includes `"baseline": "sentence_transformers_dense"` and `"model_name"`.
- **Deps:** optional `backend/requirements-retrieval-dense.txt` (install on top of `backend/requirements.txt`; pulls PyTorch via `sentence-transformers`).
- **Joint + bundle:** `scripts/phase2_eval_joint_tfidf.py --retrieval-backend dense [--dense-model …]`; `scripts/phase2_experiment_run.py --retrieval-backend dense [--dense-model …]` (intent stays TF-IDF centroid unless you swap it later).
- **Shared loop:** `scripts/phase2_retrieval_eval_core.py` — single recall@k implementation for TF-IDF and dense eval CLIs.
- **Next:** Step 12 API wiring (same index class as offline dense eval).

## Step 12 — API: dense retrieval on NLU parse

Expose **Step 11** dense chunk retrieval on **`POST /api/v1/nlu/parse`** so live `retrieval_hits` match the embedding baseline used in scripts.

- **Settings:** `COMP_LLM_RETRIEVAL_BACKEND` = `tfidf` (default) or `dense`; `COMP_LLM_DENSE_MODEL`, optional `COMP_LLM_DENSE_DEVICE`.
- **Lifespan:** `attach_retrieval_index` loads `TfidfChunkIndex` or `DenseChunkIndex` into `app.state.retrieval_index`.
- **Response:** `model` is `tfidf-baseline`, `dense-baseline`, or `stub-no-corpus` (frozen schema enum updated). Intent unchanged (`tfidf-centroid` when benchmark env is set).
- **Next:** Step 13 retrieval MRR + split merge helper.

## Step 13 — Retrieval MRR@k + merge eval splits

Tighten **retrieval** reporting and simplify **Step 10** eval file prep.

- **MRR:** `scripts/phase2_retrieval_eval_core.py` computes **mean reciprocal rank** of the **first** `gold_chunk_id` found in the top-k ranked list (0 if none). Exposed in retrieval eval JSON as **`mrr`** (same for TF-IDF and dense CLIs). Experiment bundle maps it to **`metrics.phase2_retrieval_mrr_at_k`**; leaderboard column **`retrieval_mrr`**.
- **Merge splits:** `scripts/phase2_merge_benchmark_splits.py --inputs PATH [PATH ...] -o OUT [--dedupe-example-id]` — concatenate JSONL lines in order (e.g. `benchmark_dev.jsonl` then `benchmark_test.jsonl`) for a single `--benchmark` eval file.
- **Next:** Step 14 law-grounded `/query` with citations.

## Step 14 — API: `POST /api/v1/query` (retrieval + citation excerpts)

RAG-style **evidence** for advisors: same **`retrieval_index`** as NLU parse, plus **chunk text** from `COMP_LLM_CORPUS_JSONL` (loaded once as `chunk_id` → text).

- **Route:** `POST /api/v1/query` — body: `question`, optional `top_k`. Response: `citations[]` with `chunk_id`, `score`, `text` (excerpt; cap via **`COMP_LLM_QUERY_CITATION_MAX_CHARS`**, default 2000).
- **Gateway:** `POST /api/v1/llm/query` → language-model (same proxy strip as `/nlu/parse`).
- **Code:** `app/services/corpus_chunk_texts.py`, `app/schemas/query_v1.py`, `app/routers/query.py`; lifespan sets `app.state.chunk_text_by_id`.
- **Contracts:** `evaluation/frozen/query_request.schema.json`, `query_response.schema.json`; `retrieval_model` enum matches NLU parse (`tfidf-baseline` / `dense-baseline` / `stub-no-corpus`).
- **No LLM generation** in this step — citations only; answer synthesis is a later milestone.

## Goal

Compare **candidate models** (NLU, embeddings, optional SLM) on the tasks above. For retrieval tasks, success means **grounding**: retrieved or cited chunks overlap **`gold_chunk_ids`** from `corpus_v1`. For intent tasks, success means agreement with **`gold_intent`** (alias: `intent` when no `gold_intent`).

## Workstreams

| # | Workstream | Outcome |
|---|------------|---------|
| 1 | **Benchmark governance** | JSONL schema, validator, **Step 9** `phase2_split_benchmark.py` → train/dev/test files |
| 2 | **Retrieval baselines** | TF-IDF + **Step 11** dense (`dense_chunk_index.py`, `phase2_eval_retrieval_dense.py`); optional encoders in `models/` |
| 3 | **NLU / intent** | Label set, encoder baseline or small classifier; metrics + error analysis |
| 4 | **Service API** | `POST /api/v1/nlu/parse` + **Step 14** `POST /api/v1/query` (citations); gateway `/api/v1/llm/**` |
| 5 | **Experiment tracking** | `experiment_run_template.json` + `phase2_experiment_run.py` → `phase2_runs.jsonl` |
| 6 | **Report** | `phase2_leaderboard.py` → Markdown/JSON/CSV from `phase2_runs.jsonl` |
| 7 | **Regression** | `phase2_regression_smoke.py` + `evaluation/fixtures/phase2_smoke/` + GitHub Action |
| 8 | **Handoff** | `phase2_export_handoff.py` → `evaluation/phase2_handoff/REPORT.md` |
| 9 | **Splits** | `phase2_split_benchmark.py` → reproducible train/dev/test JSONL |
| 10 | **Held-out eval** | Train intent on `*_train.jsonl`; score intent + joint on eval JSONL; experiment bundle flag |
| 11 | **Dense retrieval** | Sentence-transformers index + eval CLI; joint/bundle `--retrieval-backend dense` |
| 12 | **API dense retrieval** | `COMP_LLM_RETRIEVAL_BACKEND` + `retrieval_index` in NLU parse |
| 13 | **MRR + merge splits** | `mrr` in retrieval eval; `phase2_merge_benchmark_splits.py` for dev+test → eval |
| 14 | **Query + citations** | `/api/v1/query` with excerpted corpus text; frozen query schemas |

## Milestones (suggested order)

1. **M1 — Validate & freeze seed benchmark** — expert-checked `gold_chunk_ids`, `evaluation/benchmark_v1_dev.jsonl`
2. **M2 — TF-IDF retrieval eval** — `scripts/phase2_eval_retrieval_tfidf.py` → recall@k, MRR
3. **M3 — Dense retrieval** — same eval harness, new encoder
4. **M4 — NLU joint eval** — `scripts/phase2_eval_joint_tfidf.py` → `joint_success` (+ component rates)
5. **M5 — Gate** — **done (2026-05-11):** baseline = TF-IDF retrieval + TF-IDF centroid intent; frozen schemas under `evaluation/frozen/`; promotion rule in `phase2_M5_baseline.json`; runbook section **Phase 2 M5**.

## What is implemented now (starter)

- **Step 1 task registry** + benchmark **`task_id`** column (see seed template)
- Benchmark ↔ corpus **validation** script (task shape + chunk membership)
- **TF-IDF** retrieval baseline + **eval script** (recall@k, per-task counts)
- **Step 2** TF-IDF **intent** centroid classifier + **eval script** (LOOCV / holdout, accuracy + macro F1)
- **Step 3** **Joint** eval: intent ∧ retrieval@k on `joint_nlu_retrieval` (`phase2_eval_joint_tfidf.py`)
- **Step 4** **API** `predicted_intent` + `intent_model` via `COMP_LLM_INTENT_BENCHMARK_JSONL`
- **Step 5** **Experiment bundle** `phase2_experiment_run.py` → append to `evaluation/phase2_runs.jsonl`
- **M5 Gate** — `evaluation/frozen/phase2_M5_baseline.json` + request/response JSON Schemas + contract tests
- **Step 6** **Leaderboard** — `scripts/phase2_leaderboard.py` (quality, latency, cost columns)
- **Step 7** **Regression smoke** — `scripts/phase2_regression_smoke.py`, fixtures, `.github/workflows/phase2-smoke.yml`
- **Step 8** **Handoff report** — `scripts/phase2_export_handoff.py` → `evaluation/phase2_handoff/REPORT.md`
- **Step 9** **Benchmark splits** — `scripts/phase2_split_benchmark.py` (explicit or hashed folds)
- **Step 10** **Held-out train/eval** — `--train-benchmark` / `--intent-train-benchmark` on intent, joint, and `phase2_experiment_run.py`
- **Step 11** **Dense retrieval** — `DenseChunkIndex`, `phase2_eval_retrieval_dense.py`, `phase2_retrieval_eval_core.py`; optional `requirements-retrieval-dense.txt`
- **Step 12** **API dense retrieval** — `COMP_LLM_RETRIEVAL_BACKEND`, `attach_retrieval_index`, response `model` ∈ {`tfidf-baseline`, `dense-baseline`, `stub-no-corpus`}
- **Step 13** **MRR@k + merge splits** — retrieval JSON `mrr`, `phase2_retrieval_mrr_at_k` in bundle; `phase2_merge_benchmark_splits.py`
- **Step 14** **Query + citations** — `POST /api/v1/query`, `corpus_chunk_texts.py`, frozen `query_*.schema.json`
- **Language-model API**: `POST /api/v1/nlu/parse`, `POST /api/v1/query` (corpus + backend via env)
- **API gateway** proxy: `/api/v1/llm/**` → language-model service

## Commands

See **Phase 2** section in [PHASES_RUNBOOK.md](PHASES_RUNBOOK.md).
