# Adaptive Tax (Component 5)

AI-assisted adaptive tax calculation with explainable legal grounding.

**Port:** 8005  
**Package:** `adaptive_tax_app` (avoids pytest `app` name collisions with other components)  
**Gateway:** `/api/v1/adaptive-tax/**` → `COMP_ADAPTIVE_TAX_URL`

## Architecture guard (Phase 10) — CURRENT vs FUTURE

```text
CURRENT:
  RAG / Chroma  →  legal evidence + explain narrative
  Rule Engine   →  tax calculate (sole calculator — do not remove or bypass)
  GPT           →  optional manual corpus metadata enrich OR explain narrative
                   (never calculates tax; never writes executable params)

FUTURE (not wired):
  RAG → LegalRuleEvidence (structured legal evidence, non-executable)
      → human / admin validation
      → approved rule candidate
      → incorporation into Rule Engine / param packs
```

**Locked rules:** calc path unchanged; evidence gates (global + step) preserved; no GPT enrich → Rule Engine path. Guards live in [`architecture_guard.py`](adaptive_tax_app/services/architecture_guard.py) and [`tests/test_architecture_guard.py`](tests/test_architecture_guard.py).

**Phase 11a:** [`LegalRuleEvidence`](adaptive_tax_app/schemas/legal_rule_evidence.py) = structured legal evidence from RAG (not RAG calculation). Default `status=candidate`, `executable=false`; numeric caps/thresholds only when literally present in `source_quote`.

**Phase 11b (stub):** Human/admin approval path for future rule candidates — [`legal_rule_evidence_review.py`](adaptive_tax_app/services/legal_rule_evidence_review.py). Aligns with amendment `approve` / `reject` UX terminology. Approving never mutates param packs, Neo4j executable edges, or `POST /calculate`. `incorporate_into_engine_stub` returns `blocked_future_only`.

**Phase 11c:** Optional `legal_rule_evidence` candidates on the explain [`EvidenceBundle`](adaptive_tax_app/schemas/evidence.py) (IDs + section/paragraph/YA; formula/cap null until validated). Emission: [`legal_rule_evidence_emit.py`](adaptive_tax_app/services/legal_rule_evidence_emit.py). Docs never label this as calculation.

Acceptance checklist: [`evaluation/adaptive-tax/rag/ACCEPTANCE_CHECKLIST.md`](../../evaluation/adaptive-tax/rag/ACCEPTANCE_CHECKLIST.md).

## Phase status

**Phase 1:** Amendment pipeline (upload → extract → review → approve/reject into PostgreSQL).

**Phase 2:** Neo4j Desktop + embedded Chroma; approve merges `MODIFIES` edges; `/knowledge/*` debug APIs.

**Phase 3:** Pure-Python rule engine + calculator (`POST /api/v1/calculate`); KG + param JSON; no GPT. UI at `/adaptive-tax/calculator`.

**Phase 4:** Explanation engine + report UI + viva demo script + evaluation package + recording checklist. See [`evaluation/adaptive-tax/`](../../evaluation/adaptive-tax/) and runbook viva sections.

**Phase 5.0 (in progress):** Dual YA packs (`2024_25` / `2025_26`), section-scoped Act harvest CLI, coverage checklist + scorer, provenance data contract (`rule_source_id` on packs; `COMP_ADAPTIVE_TAX_PROVENANCE_MODE=legacy`). Master PDF demoted from explain. See [`evaluation/adaptive-tax/phase5/`](../../evaluation/adaptive-tax/phase5/).

**Phase 5.7:** Investment income — Sec 7 base path + optional Sec 7(3)(a) final-WHT exclusion. Coverage **7/8**. Goldens ex15, ex16.

**Phase 5.6:** Business income — 5.6a net input + 5.6b optional gross/deductions/CA (Act-gated). Coverage **6/8**. Goldens ex02, ex13, ex14. **Store sync:** after each Phase 5 area run `scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j` (add `--apply-chroma --chroma-smoke` when corpus changes).

**Phase 6.4:** Business card + minimal catalog (`biz_net_profits`, `biz_gross`, `biz_deductions`, `biz_capital_allowances`) → normalize → existing Sec 6/11/16 net path. Golden ex24.

**Phase 6.5:** Other Income (Sec 8) — `other_income` / `other_final_withholding` scalars + catalog residual/custom sources at **Medium** confidence (`oth_residual`, `oth_custom`, `oth_final_withholding`). Golden ex25.

**Phase 6.6:** Field explain drawer + confidence badges — `GET /filing-catalog/{component_id}/explain` returns section, Act quote, KG node ids, Chroma evidence envelope, `legal_confidence` + `confidence_basis` + reason. Calculator **Explain** opens a side drawer per catalog field.

**Phase 6.7:** Fifth Sch paragraph 2 reliefs on a **Statutory Reliefs** card (not QP): 2(g) solar Rs 600,000 resident-only both YAs; 2(c) rent `min(claimed, floor(0.25 × included inv_rents))`. Order QP → solar → rent → personal relief 2(a). 2(f) sunset skipped. Goldens **ex26** (stack/floor, dual YA), **ex27** (per-category QP 1(a)+1(b)+1(d), no aggregate pool), **ex28/ex29** (unresolved KG), **ex30** (rent vs FWH).

**Phase 5.5:** Charitable donations live as Fifth Sch **1(a)** (`qp_approved_charitable`): `min(claimed, 75000, floor(assessable/3))`. Standalone Donations card retired. Coverage **5/8**.

**Phase 5.4:** Sec 52 qualifying payments — Fifth Sch para 1 per-category limits only (Path B: **no fictional aggregate cap**); Sec 52(4) CF when assessable income insufficient (Act 11/2026, YA 2025/26). Golden `ex10`.

**Phase 5.3:** Personal relief Act-verified (YA24 **1.2M**; YA25 **1.8M** Act 02/2025). Resident-only handler + approve writer; viva T1≠T2 via `reset-to-pre-amend`. Coverage **3/8**.

**Phase 5.2:** First Schedule rates Act-verified (YA24 includes 12%; YA25 1M@6%). Rate approve writer + ex09 band edges. Coverage **2/8**.

**Phase 5.1:** Employment Sec 5 path — Act-backed contribution + optional Sec 5(3)(a) final-WHT exclusion (`employment_final_withholding`). Coverage `employment_income` = covered. Golden `ex12`.

**Phase 5.0b:** Provenance gate in the rule engine — bootstrap Act quotes in [`models/adaptive-tax/fixtures/provenance_bootstrap_v1.json`](../../models/adaptive-tax/fixtures/provenance_bootstrap_v1.json); strict mode refuses unlinked tax math. Scorer: [`evaluation/adaptive-tax/provenance/score_provenance.py`](../../evaluation/adaptive-tax/provenance/score_provenance.py).

Canonical commands: [`docs/PHASES_RUNBOOK.md`](../../docs/PHASES_RUNBOOK.md) (Adaptive Tax sections).

## Setup

```powershell
.\.venv-backend\Scripts\python.exe -m pip install -r backend/comp-adaptive-tax/requirements-adaptive-tax.txt
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
```

Set `COMP_ADAPTIVE_TAX_EXTRACTION_MODE=fixture` (offline) or `openai` (+ `OPENAI_API_KEY`) in `.env`.

### Phase 2 stores (Neo4j Desktop + embedded Chroma)

**Default demo path** (no Docker):

1. Install [Neo4j Desktop](https://neo4j.com/download/), create a Neo4j **5.x / 2025+** DBMS, password e.g. `adaptive-tax-dev`, **Start**.
2. Confirm [http://127.0.0.1:7474](http://127.0.0.1:7474) and Bolt `bolt://127.0.0.1:7687`.
3. Copy Neo4j / Chroma keys from [`.env.example`](../../.env.example) into `.env`.

Embedded Chroma persists under `data/processed/adaptive-tax/chroma`. Optional Docker profile `adaptive-tax` in [`docker/docker-compose.yml`](../../docker/docker-compose.yml) is for teammates with working Docker only.

### Phase 3 — Rule engine env

| Var | Default | Purpose |
|-----|---------|---------|
| `COMP_ADAPTIVE_TAX_ONTOLOGY_DIR` | `models/adaptive-tax/ontology` | Rate bands, relief caps, calc edges |
| `COMP_ADAPTIVE_TAX_KG_MODE` | `auto` | `auto` applies to `get_kg_client()` default / tests / explain (`auto` → Neo4j when `NEO4J_PASSWORD` is set, else file ontology). **HTTP `POST /calculate` always forces `neo4j`** (503 if Desktop is down; no file-ontology fallback on that route). |

**YA packs (Phase 5.0):** `assessment_year=2024_25` → personal relief **1.2M**; `2025_26` → personal relief **1.8M** (Act 02/2025). Sec 52 QP uses Fifth Sch para 1 category limits only — no aggregate cap rows in relief JSON. Files: `relief_caps_2024_25.json`, `relief_caps_2025_26.json`, `rate_bands_2025_26.json`.

### Phase 5.0 — Section harvest (official Acts)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_EXTRACTION_MODE = "fixture"   # or openai
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_section_harvest.py `
  --section 52 --source-doc-id ird-ira-2017-base --dry-run
```

### RAG corpus — GPT metadata assist (manual, optional)

**Not** part of corpus rebuild. Required path: PDF → deterministic chunking/metadata → Chroma → eval. Only if `needs_review` chunks remain after that, a human may run:

```powershell
# List candidates (no API key)
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_enrich_corpus_metadata.py --dry-run

# Apply validated GPT metadata to a new JSONL (never auto-writes live corpus)
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_enrich_corpus_metadata.py `
  --apply --out data/processed/adaptive-tax/corpus_v1.gpt_enriched.jsonl
```

Rejects invented sections/dates; never feeds the Rule Engine; re-index Chroma only after you accept the enriched file (`adaptive_tax_build_chroma.py --reset`). CI/offline corpus build does not require `OPENAI_API_KEY`.

Coverage score:

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/coverage/score_coverage.py
```

### Phase 4 — Explanation / report env

| Var | Default | Purpose |
|-----|---------|---------|
| `COMP_ADAPTIVE_TAX_EXPLAIN_MODE` | `fixture` | `fixture` (offline template) \| `openai` (evidence-only narrative) |
| `COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL` | `gpt-4o-mini` | Model for explain when mode is `openai` |
| `COMP_ADAPTIVE_TAX_CALC_STORE_DIR` | `data/processed/adaptive-tax/calculations` | JSON store keyed by `calc_id` |
| `COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH` | `data/processed/adaptive-tax/active_relief_caps.json` | Runtime personal relief override (viva T1≠T2) |
| `COMP_ADAPTIVE_TAX_PROVENANCE_MODE` | `legacy` | `legacy` \| `strict` (Phase 5.0b gate) |
| `COMP_ADAPTIVE_TAX_AMENDMENT_STORE` | `postgres` | `postgres` (default) \| `file` (JSON jobs, no DB for amendments) |
| `COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR` | `data/dev/amendment-jobs` | Directory for file-store amendment job JSON |

### Amendment demo without PostgreSQL

When Azure/local Postgres is unavailable, run the full upload → extract → review → approve/reject flow using the file store:

```powershell
# In repo-root .env
COMP_ADAPTIVE_TAX_AMENDMENT_STORE=file
COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR=data/dev/amendment-jobs
COMP_ADAPTIVE_TAX_EXTRACTION_MODE=fixture
```

Restart Adaptive Tax on `:8005`, then open [http://localhost:5173/adaptive-tax/admin/upload](http://localhost:5173/adaptive-tax/admin/upload).

PDFs land under `COMP_ADAPTIVE_TAX_UPLOAD_ROOT`; job metadata is one JSON file per job under `COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR`. Neo4j merge on approve is best-effort (graceful `neo4j_unavailable` if Desktop is off).

When Postgres is ready again, set `COMP_ADAPTIVE_TAX_AMENDMENT_STORE=postgres` (or remove the var) and run `alembic upgrade head`.


```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

## Key URLs

| Path | Purpose |
|------|---------|
| `http://127.0.0.1:8005/health` | Direct liveness |
| `http://127.0.0.1:8000/api/v1/adaptive-tax/health` | Via API gateway |
| `POST /api/v1/calculate` | Phase 3 tax calc (always Neo4j; 503 if Desktop is down) + trace (+ Phase 4 `calc_id`) |
| `GET /api/v1/calculations/{calc_id}` | Phase 4 reload persisted calculation |
| `POST /api/v1/explain` | Phase 4 RAG-grounded narrative (`fixture` \| `openai`) |
| `POST /api/v1/admin/params/reset-to-pre-amend` | Phase 4 seed pre-amend personal relief (1.2M) for viva T1 |
| `POST /api/v1/admin/amendments/upload` | Upload PDF (gateway: prefix `/adaptive-tax`) |
| `POST /api/v1/admin/amendments/{id}/extract` | Extract rules |
| `GET /api/v1/admin/amendments/{id}` | Review payload |
| `POST .../approve` / `.../reject` | Finalize (Postgres or file store) + Neo4j/Chroma merge on approve |
| `GET /api/v1/knowledge/graph-stats` | Node/edge counts |
| `POST /api/v1/knowledge/rag/search` | Chroma RAG search |
| [http://localhost:5173/adaptive-tax/calculator](http://localhost:5173/adaptive-tax/calculator) | Phase 3 calculator UI |
| [http://localhost:5173/adaptive-tax/report/:calcId](http://localhost:5173/adaptive-tax/report/:calcId) | Phase 4 report UI |
| [http://localhost:5173/adaptive-tax/admin/upload](http://localhost:5173/adaptive-tax/admin/upload) | Admin UI |

### Calculate smoke

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"1800000","param_set":"current"}'
# Expect final_tax_lkr = "48000"
```

Via gateway: `POST http://127.0.0.1:8000/api/v1/adaptive-tax/calculate`.

## Tests

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_EXTRACTION_MODE = "fixture"
# pytest-only: file ontology so unit tests do not require Neo4j Desktop.
# Live HTTP POST /calculate always forces neo4j (see env table above).
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests -q --tb=short

# Unit only (skip Postgres integration):
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests -q -m "not integration"

# Phase 3 named examples (ex01–ex08):
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

Fixtures live under [`models/adaptive-tax/examples/`](../../models/adaptive-tax/examples/).

### Phase 4 viva demo script

```powershell
# Server must be running on :8005 (fixture extract/explain recommended)
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf
```

Run this suite **separately** from other components.

## Boundary

Component 2 (tax optimization) remains on port **8002** / `/api/v1/optimization/**` / `/tax/*`. Do not modify `backend/comp-tax-optimization/`, `frontend/src/features/tax-optimization/`, or `models/tax-optimization/`.
