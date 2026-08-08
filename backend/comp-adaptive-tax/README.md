# Adaptive Tax (Component 5)

AI-assisted adaptive tax calculation with explainable legal grounding.

**Port:** 8005  
**Package:** `adaptive_tax_app` (avoids pytest `app` name collisions with other components)  
**Gateway:** `/api/v1/adaptive-tax/**` → `COMP_ADAPTIVE_TAX_URL`

## Phase status

**Phase 1:** Amendment pipeline (upload → extract → review → approve/reject into PostgreSQL).

**Phase 2:** Neo4j Desktop + embedded Chroma; approve merges `MODIFIES` edges; `/knowledge/*` debug APIs.

**Phase 3:** Pure-Python rule engine + calculator (`POST /api/v1/calculate`); KG + param JSON; no GPT. UI at `/adaptive-tax/calculator`.

**Phase 4:** Explanation engine + report UI + viva demo script + evaluation package + recording checklist. See [`evaluation/adaptive-tax/`](../../evaluation/adaptive-tax/) and runbook viva sections.

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
| `COMP_ADAPTIVE_TAX_KG_MODE` | `auto` | `auto` / `neo4j` / `file` (`auto` → Neo4j when password set) |

If Neo4j is up but missing Phase 3 `CONTRIBUTES_TO` edges, the engine falls back to the file ontology so tax is not silently zero.

### Phase 4 — Explanation / report env

| Var | Default | Purpose |
|-----|---------|---------|
| `COMP_ADAPTIVE_TAX_EXPLAIN_MODE` | `fixture` | `fixture` (offline template) \| `openai` (evidence-only narrative) |
| `COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL` | `gpt-4o-mini` | Model for explain when mode is `openai` |
| `COMP_ADAPTIVE_TAX_CALC_STORE_DIR` | `data/processed/adaptive-tax/calculations` | JSON store keyed by `calc_id` |
| `COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH` | `data/processed/adaptive-tax/active_relief_caps.json` | Runtime Sec 52 cap override (viva T1≠T2) |

## Startup

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
| `POST /api/v1/calculate` | Phase 3 tax calc + calculation trace (+ Phase 4 `calc_id`) |
| `GET /api/v1/calculations/{calc_id}` | Phase 4 reload persisted calculation |
| `POST /api/v1/explain` | Phase 4 RAG-grounded narrative (`fixture` \| `openai`) |
| `POST /api/v1/admin/params/reset-to-pre-amend` | Phase 4 seed pre-amend Sec 52 cap (1.2M) for viva T1 |
| `POST /api/v1/admin/amendments/upload` | Upload PDF (gateway: prefix `/adaptive-tax`) |
| `POST /api/v1/admin/amendments/{id}/extract` | Extract rules |
| `GET /api/v1/admin/amendments/{id}` | Review payload |
| `POST .../approve` / `.../reject` | Finalize in Postgres (+ Neo4j/Chroma merge on approve) |
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
