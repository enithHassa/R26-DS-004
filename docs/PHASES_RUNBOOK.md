# Phase runbook — Intelligent Tax Advisory Language Model (Component 4)

This file is the **single place** for copy-paste commands for **Phase 1 onward**.  
**Update it when you add Phase 2, 3, … steps** so the team stays aligned.

**Convention:** run everything from the **repository root** unless noted. On Windows, examples use **PowerShell**.

---

## Prerequisites

- **Python 3.11+**
- Backend virtualenv at `.venv-backend` (create if needed):

  ```powershell
  python -m venv .venv-backend
  .\.venv-backend\Scripts\Activate.ps1
  pip install -r backend/requirements.txt
  ```

- **`PYTHONPATH`:** the commands below set it only where required (multiple packages named `app` live under `backend/`).

---

## Dashboard — frontend + backends (tax optimization / recommendation)

The Vite app in `frontend/` proxies **`/api`** to the **API gateway** (default `http://127.0.0.1:8000`) and **`/api/v1/optimization`** directly to **Component B** on port **8002** (see `frontend/vite.config.ts`).

**1. Install JS deps (once):**

```powershell
cd frontend
npm install
cd ..
```

**2. Start backends** (four terminals, or run in background). From repo root, `PYTHONPATH` must include the repo root:

```powershell
$env:PYTHONPATH = "$PWD"

# Component B — tax optimization (port 8002)
.\.venv-backend\Scripts\python.exe -m uvicorn tax_opt_b_app.main:app --app-dir backend/comp-tax-optimization --host 127.0.0.1 --port 8002

# Component 3 — personalized recommendation (port 8003)
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/comp-personalized-recommendation --host 127.0.0.1 --port 8003

# API gateway (port 8000)
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/api-gateway --host 127.0.0.1 --port 8000
```

**3. Start frontend:**

```powershell
cd frontend
npm run dev
```

- **UI:** [http://127.0.0.1:5173/](http://127.0.0.1:5173/) (Vite may open `/tax-optimization/explorer` automatically).
- **Gateway health:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **`/ready`:** may show `"degraded"` if **transaction** (default `http://127.0.0.1:8001`) is not running; that is OK if you only use optimization + recommendation routes.

**If a service fails to start with `ModuleNotFoundError`:** run `pip install -r backend/requirements.txt` again (the lockfile includes `PyYAML`, `joblib`, `scikit-learn`, `pandas` needed by these apps).

---

## Adaptive Tax (Component 5) — Phase 1 amendment pipeline

Admin can upload an amendment PDF, extract structured rules with `source_quote`, review in the UI, and approve/reject into PostgreSQL. Phase 2 adds Neo4j Desktop + embedded Chroma (see below). Port **8005**; Comp 2 optimization on **8002** is unchanged.

### One-time setup

```powershell
# Extras (pymupdf, openai) on top of backend/requirements.txt
.\.venv-backend\Scripts\python.exe -m pip install -r backend/comp-adaptive-tax/requirements-adaptive-tax.txt

# Schema (requires DATABASE_MODE=azure|local — not sqlite)
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
```

`.env` knobs (see `.env.example`):

| Var | Notes |
|-----|--------|
| `COMP_ADAPTIVE_TAX_EXTRACTION_MODE` | `fixture` (offline / viva dry-run) or `openai` |
| `COMP_ADAPTIVE_TAX_OPENAI_MODEL` | default `gpt-4o-mini` |
| `OPENAI_API_KEY` | required only when mode=`openai` |
| `COMP_ADAPTIVE_TAX_UPLOAD_ROOT` | default `~/.ai-tax-advisory/uploads/comp-adaptive-tax` |

### Start Adaptive Tax (:8005)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_EXTRACTION_MODE = "fixture"   # or openai
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

Also start gateway (`:8000`) and frontend (`npm run dev` in `frontend/`) for the UI demo.

### Smoke + Week 1 demo (curl)

```powershell
# Health
Invoke-RestMethod http://127.0.0.1:8005/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/adaptive-tax/health

# Upload → extract → get → approve (fixture mode; use a real amendment PDF path)
$pdf = "path\to\IR_Act_No_02-2025_E.pdf"
$upload = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8005/api/v1/admin/amendments/upload `
  -Form @{ file = Get-Item $pdf }
$jobId = $upload.id
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8005/api/v1/admin/amendments/$jobId/extract"
Invoke-RestMethod "http://127.0.0.1:8005/api/v1/admin/amendments/$jobId"
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8005/api/v1/admin/amendments/$jobId/approve"
# Reject instead: POST .../reject with body @{ reason = "..." }
```

Via gateway, prefix paths with `/api/v1/adaptive-tax` (e.g. `/api/v1/adaptive-tax/admin/amendments/upload`).

### UI demo

| Page | URL |
|------|-----|
| Home | [http://localhost:5173/adaptive-tax/home](http://localhost:5173/adaptive-tax/home) |
| Calculator | [http://localhost:5173/adaptive-tax/calculator](http://localhost:5173/adaptive-tax/calculator) |
| Upload | [http://localhost:5173/adaptive-tax/admin/upload](http://localhost:5173/adaptive-tax/admin/upload) |
| Review | `/adaptive-tax/admin/review/:jobId` (after Extract) |

Flow: pick PDF → Upload → Extract → review side-by-side rules vs source quotes → Approve / Reject.

Vite proxies `/api/v1/adaptive-tax` to `:8005` (`frontend/vite.config.ts`).

### Tests

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_EXTRACTION_MODE = "fixture"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests -q --tb=short

# Unit only (skip Postgres integration):
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests -q -m "not integration"
```

Run this suite **separately** (never mix with other `app` packages in one pytest command).

### Phase 2 — Knowledge stores (Neo4j Desktop + embedded Chroma)

**Default (demo / this laptop):** Neo4j Desktop + embedded Chroma on disk. Docker is optional for teammates whose WSL2/virt works.

#### Step 0b — Neo4j Desktop

1. Install [Neo4j Desktop](https://neo4j.com/download/) (AMD64 / x64).
2. Create a local DBMS (Neo4j **5.x**), set password (e.g. `adaptive-tax-dev`), click **Start**.
3. Confirm Browser: [http://127.0.0.1:7474](http://127.0.0.1:7474) and Bolt `neo4j://127.0.0.1:7687`.

```powershell
# Session env (or put the same keys in repo-root .env — see .env.example)
$env:NEO4J_URI = "neo4j://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"
$env:CHROMA_PERSIST_DIR = "data/processed/adaptive-tax/chroma"
$env:CHROMA_COLLECTION = "ird_legal_evidence_v1"
$env:COMP_ADAPTIVE_TAX_CORPUS_JSONL = "data/processed/adaptive-tax/corpus_v1.jsonl"
```

| Var | Default | Purpose |
|-----|---------|---------|
| `NEO4J_URI` | `neo4j://127.0.0.1:7687` | Desktop or Docker Neo4j |
| `NEO4J_USER` | `neo4j` | Auth user |
| `NEO4J_PASSWORD` | (required) | Match Desktop DBMS password |
| `CHROMA_PERSIST_DIR` | `data/processed/adaptive-tax/chroma` | Embedded Chroma folder |
| `CHROMA_COLLECTION` | `ird_legal_evidence_v1` | Collection name |
| `COMP_ADAPTIVE_TAX_CORPUS_JSONL` | `data/processed/adaptive-tax/corpus_v1.jsonl` | Adaptive-tax corpus |

Settings live in `backend/comp-adaptive-tax/adaptive_tax_app/config.py` (same `.env` as the rest of the monorepo).

#### Optional Docker (teammates only)

```powershell
docker compose -f docker/docker-compose.yml --profile adaptive-tax up -d neo4j chromadb
# Neo4j :7474 / :7687 — Chroma HTTP :8006 (app default remains embedded Chroma)
```

Acceptance for Phase 2 does **not** require Docker. Prefer Desktop + embedded Chroma for demos on other laptops.

#### Step A — Corpus build

PDFs live under `data/raw/adaptive-tax/` (gitignored). Manifest: [`models/adaptive-tax/corpus_manifest.json`](../models/adaptive-tax/corpus_manifest.json).

```powershell
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_build_corpus.py
# Output: data/processed/adaptive-tax/corpus_v1.jsonl (+ text extracts under data/processed/adaptive-tax/text/)
```

#### Step B — Neo4j legal layer

Neo4j Desktop must be **running** (`NEO4J_PASSWORD` matches `.env`). Prefer `bolt://127.0.0.1:7687` if `neo4j://` routing retries appear.

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"   # or rely on .env
.\.venv-backend\Scripts\python.exe scripts/neo4j_apply_schema.py
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_corpus_chunks.py `
  --corpus-jsonl data/processed/adaptive-tax/corpus_v1.jsonl
```

Browser sanity:

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(*) ORDER BY count(*) DESC;
MATCH (l:LawInstrument) RETURN l.source_doc_id;
```

#### Step C — Minimal calculation ontology

Hand-authored under `models/adaptive-tax/ontology/` (`rate_bands_2024_25.json`, `relief_caps.json`, `concepts_mvp.json`, `mvp_calc_edges_seed.jsonl`).

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_calc_ontology_nodes.py
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_curated_edges.py `
  --edges-jsonl models/adaptive-tax/ontology/mvp_calc_edges_seed.jsonl `
  --warn-miss
```

Expect calc edges including `DEFINES` / `COVERS_RELIEF` / `APPLIES_TO` plus Phase 3 `CONTRIBUTES_TO` / `DEDUCTED_FROM` / `LIMITED_BY` (Sec 52 cap **1_800_000**, personal relief **1_200_000**, donation **33%** of assessable, five First Schedule bands).

#### Step D — Embedded Chroma index

```powershell
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_build_chroma.py --reset
# Smoke:
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_build_chroma.py `
  --smoke-query "qualifying payment" --smoke-section "52"
```

Persists under `data/processed/adaptive-tax/chroma` (collection `ird_legal_evidence_v1`). Runtime helpers: `adaptive_tax_app/services/chroma_index.py`.

#### Step E — Approve → graph merge + debug APIs

With Neo4j Desktop running and Chroma indexed:

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

```powershell
# Graph stats (~30–50 calc edges)
Invoke-RestMethod http://127.0.0.1:8005/api/v1/knowledge/graph-stats

# RAG search
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/knowledge/rag/search `
  -ContentType "application/json" `
  -Body '{"section_ref":"52","query":"qualifying payment","top_k":5}'

# Approve a fixture extraction → merge.merged should be true when Neo4j is up
# (see Phase 1 smoke: upload → extract → approve)
```

Neo4j Browser after approve:

```cypher
MATCH (a:LawInstrument)-[r:MODIFIES]->(s:Section)
RETURN a.source_doc_id, r.review_status, s.section_uid;
```

**Demo laptop (no Docker):** Neo4j Desktop + `.env` Neo4j/Chroma keys + rebuild corpus/Chroma from PDFs (`adaptive_tax_build_corpus.py`, `adaptive_tax_build_chroma.py`) or copy `data/processed/adaptive-tax/`.

Via gateway: `/api/v1/adaptive-tax/knowledge/...`.

### Phase 3 — Rule engine + calculator (no GPT)

Pure-Python tax calculation driven by the Phase 2 calc ontology (Neo4j or file mirror) plus param JSON (`rate_bands_2024_25.json`, `relief_caps.json`, `relief_caps_pre_amend_2025.json`). Frontend: `/adaptive-tax/calculator`.

#### Env

| Var | Default | Purpose |
|-----|---------|---------|
| `COMP_ADAPTIVE_TAX_ONTOLOGY_DIR` | `models/adaptive-tax/ontology` | Concepts, edges, rate bands, relief caps |
| `COMP_ADAPTIVE_TAX_KG_MODE` | `auto` | `auto` (Neo4j if password set, else file) \| `neo4j` \| `file` |

Force offline/unit behaviour with `COMP_ADAPTIVE_TAX_KG_MODE=file`.

#### Reload Phase 3 calc ontology into Neo4j

After pulling new `CONTRIBUTES_TO` / `DEDUCTED_FROM` / `LIMITED_BY` edges (or new concepts):

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_calc_ontology_nodes.py
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_curated_edges.py `
  --edges-jsonl models/adaptive-tax/ontology/mvp_calc_edges_seed.jsonl --warn-miss
```

If Neo4j is missing those edges, `POST /calculate` falls back to the file ontology so income is not dropped (avoids silent tax `0`).

#### Start Adaptive Tax (:8005)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "auto"   # or file for offline
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

Also start gateway (`:8000`) and frontend (`npm run dev` in `frontend/`) for the UI.

#### Calculate smoke (curl / PowerShell)

```powershell
# Direct
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"1800000","business_income":"0","investment_income":"0","qualifying_payments":"0","donations":"0","param_set":"current"}'
# Expect: final_tax_lkr = "48000"; rules include sum_assessable, apply_personal_relief, slab_band_1, slab_band_2, final_tax

# Via gateway
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/adaptive-tax/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"1800000","param_set":"current"}'
```

Pipeline (legal order): sum assessable → QP / donation caps → personal relief (residents) → progressive slabs from `rate_bands_2024_25.json`.

#### UI

| Page | URL |
|------|-----|
| Calculator | [http://localhost:5173/adaptive-tax/calculator](http://localhost:5173/adaptive-tax/calculator) |
| Home (CTA) | [http://localhost:5173/adaptive-tax/home](http://localhost:5173/adaptive-tax/home) |

No GPT / RAG on the calculator page — only `POST /calculate` + calculation trace.

#### Named examples (pytest)

Fixtures: [`models/adaptive-tax/examples/`](../models/adaptive-tax/examples/) (`ex01`–`ex08`).

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_rule_engine_examples.py -q --tb=short
```

### Phase 4 — Explanation engine + report + evaluation

RAG-grounded narrative from the Phase 3 calculation trace + Chroma chunks + Postgres `rule_source` quotes. Report UI, viva demo script, and evaluation harness are in place (Steps 0–8).

#### Env (config landed)

| Var | Default | Purpose |
|-----|---------|---------|
| `COMP_ADAPTIVE_TAX_EXPLAIN_MODE` | `fixture` | `fixture` (offline/viva template) \| `openai` (requires `OPENAI_API_KEY`) |
| `COMP_ADAPTIVE_TAX_OPENAI_EXPLAIN_MODEL` | `gpt-4o-mini` | Model for explain when mode is `openai` |
| `COMP_ADAPTIVE_TAX_CALC_STORE_DIR` | `data/processed/adaptive-tax/calculations` | Persisted calc JSON keyed by `calc_id` |
| `COMP_ADAPTIVE_TAX_PARAM_OVERRIDE_PATH` | `data/processed/adaptive-tax/active_relief_caps.json` | Runtime relief-cap override after Sec 52 approve |

Settings: `backend/comp-adaptive-tax/adaptive_tax_app/config.py` (`calc_store_dir`, `param_override_path`).

#### APIs (pending — fill when implemented)

| Method | Path | Status |
|--------|------|--------|
| `POST` | `/api/v1/calculate` | Done — returns `calc_id` (persists JSON under calc store) |
| `GET` | `/api/v1/calculations/{calc_id}` | Done (Step 1) — reload for report page |
| `POST` | `/api/v1/admin/params/reset-to-pre-amend` | Done (Step 2) — seed 1.2M Sec 52 cap override for viva T1 |
| — | `services/evidence.gather_evidence` | Done (Step 3) — Chroma + PG quotes + optional Neo4j MODIFIES |
| `POST` | `/api/v1/explain` | Done (Step 4) — fixture\|openai; empty evidence → `insufficient_evidence` |

Gateway prefix: `/api/v1/adaptive-tax/**`.

#### Explain smoke (Step 4)

```powershell
$env:COMP_ADAPTIVE_TAX_EXPLAIN_MODE = "fixture"
$calc = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"1800000","param_set":"current"}'
# Requires Chroma indexed (or returns insufficient_evidence: true)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/explain `
  -ContentType "application/json" `
  -Body (@{ calc_id = $calc.calc_id } | ConvertTo-Json)
```

#### Param override / T1≠T2 smoke (Step 2)

```powershell
# 1) Seed pre-amend Sec 52 cap (1.2M) into runtime override
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/admin/params/reset-to-pre-amend

# 2) ex04-style calc → T1 (expect 48000 with 1.2M cap)
$t1 = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"3000000","qualifying_payments":"2500000","param_set":"current"}'
$t1.final_tax_lkr   # "48000"

# 3) Upload + extract + approve Act 02/2025 (fixture mode writes Sec 52 override 1.8M)
# ... then re-run the same calculate body → T2 "0" (≠ T1)
```

Approve response includes `param_override` when a Sec 52 cap rule was written.

#### Calculate + calc_id smoke (Step 1)

```powershell
$calc = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8005/api/v1/calculate `
  -ContentType "application/json" `
  -Body '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"1800000","param_set":"current"}'
$calc.calc_id
$calc.final_tax_lkr   # "48000"
Invoke-RestMethod -Uri "http://127.0.0.1:8005/api/v1/calculations/$($calc.calc_id)"
```

Via gateway: `POST/GET http://127.0.0.1:8000/api/v1/adaptive-tax/...`.

#### UI

| Page | URL | Status |
|------|-----|--------|
| Report | [http://localhost:5173/adaptive-tax/report/:calcId](http://localhost:5173/adaptive-tax/report/:calcId) | Done (Step 5) — linked from calculator after calc |
| Calculator → report link | `/adaptive-tax/calculator` | Done |

#### Adaptive Tax Phase 4 — Viva demo

**Prerequisites**

1. Adaptive Tax API on `:8005` (Postgres for amendments; `COMP_ADAPTIVE_TAX_EXTRACTION_MODE=fixture` recommended).
2. Optional: gateway `:8000`, frontend `:5173`, Neo4j (for MODIFIES panel), Chroma indexed (for non-empty explain evidence).
3. Act PDF at `data/raw/adaptive-tax/IR_Act_No_02-2025_E.pdf`, **or** use `--allow-stub-pdf` with fixture extract.

**One-shot script (preferred)**

```powershell
# Terminal: Adaptive Tax already running on :8005
$env:COMP_ADAPTIVE_TAX_EXPLAIN_MODE = "fixture"   # on the server process
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf

# With real Act PDF:
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase4_demo.py `
  --pdf data/raw/adaptive-tax/IR_Act_No_02-2025_E.pdf
```

Script steps: health → `reset-to-pre-amend` → calc ex04 **T1** + `calc_id_1` → upload/extract/approve → calc **T2** (assert ≠ T1) → `POST /explain` for both ids → print report URLs.

**Manual PowerShell (copy-paste)**

```powershell
$api = "http://127.0.0.1:8005"
$fe  = "http://127.0.0.1:5173"

# 0) Health
Invoke-RestMethod "$api/health"

# 1) Seed pre-amend Sec 52 cap (1.2M)
Invoke-RestMethod -Method Post -Uri "$api/api/v1/admin/params/reset-to-pre-amend"

# 2) ex04 inputs → T1 (expect 48000 with 1.2M cap)
$ex04 = '{"assessment_year":"2024_25","resident_status":"resident","employment_income":"3000000","business_income":"0","investment_income":"0","qualifying_payments":"2500000","donations":"0","param_set":"current"}'
$t1 = Invoke-RestMethod -Method Post -Uri "$api/api/v1/calculate" -ContentType "application/json" -Body $ex04
"T1=$($t1.final_tax_lkr)  calc_id_1=$($t1.calc_id)"

# 3) Upload + extract + approve Act 02/2025
$pdf = "data\raw\adaptive-tax\IR_Act_No_02-2025_E.pdf"   # or a stub PDF in fixture mode
$upload = Invoke-RestMethod -Method Post -Uri "$api/api/v1/admin/amendments/upload" -Form @{ file = Get-Item $pdf }
$jobId = $upload.id
Invoke-RestMethod -Method Post -Uri "$api/api/v1/admin/amendments/$jobId/extract"
$approved = Invoke-RestMethod -Method Post -Uri "$api/api/v1/admin/amendments/$jobId/approve"
$approved.merge
$approved.param_override

# 4) Same inputs → T2 (expect 0 with 1.8M cap; must differ from T1)
$t2 = Invoke-RestMethod -Method Post -Uri "$api/api/v1/calculate" -ContentType "application/json" -Body $ex04
"T2=$($t2.final_tax_lkr)  calc_id_2=$($t2.calc_id)"
if ($t2.final_tax_lkr -eq $t1.final_tax_lkr) { throw "T2 must differ from T1" }

# 5) Explain both calc ids
Invoke-RestMethod -Method Post -Uri "$api/api/v1/explain" -ContentType "application/json" -Body (@{ calc_id = $t1.calc_id } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$api/api/v1/explain" -ContentType "application/json" -Body (@{ calc_id = $t2.calc_id } | ConvertTo-Json)

# 6) Report pages
"$fe/adaptive-tax/report/$($t1.calc_id)"
"$fe/adaptive-tax/report/$($t2.calc_id)"
```

Expected economics (ex04 salary 3M + QP 2.5M, `param_set=current` + override): **T1 ≈ 48000** (cap 1.2M) → **T2 = 0** (cap 1.8M).

#### Evaluation

Artifacts under [`evaluation/adaptive-tax/`](../evaluation/adaptive-tax/) (Step 7).

| Metric | Scorer |
|--------|--------|
| Extraction precision | `evaluation/adaptive-tax/extraction/score_extraction.py` |
| Calculation accuracy | `pytest .../test_rule_engine_examples.py` → `calculation/RESULTS.md` |
| Citation faithfulness | `citation_faithfulness/score_citations.py` |
| Explanation grounding | `explanation_grounding/score_grounding.py` |
| Amendment adaptivity | `amendment_adaptivity/score_adaptivity.py` |

Filled Chapter 4 table: [`evaluation/adaptive-tax/metrics_table.md`](../evaluation/adaptive-tax/metrics_table.md).

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/extraction/score_extraction.py
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/amendment_adaptivity/score_adaptivity.py
```

#### Adaptive Tax Phase 4 — Viva recording checklist (Step 8)

Deliverable: **screen-recorded viva demo** (video usually on an external drive / gitignored path). Full UI checklist below; API-only dry-run: `scripts/adaptive_tax_phase4_demo.py`.

**A. Stack up**

| Service | Port | Notes |
|---------|------|-------|
| Adaptive Tax | `:8005` | `COMP_ADAPTIVE_TAX_EXTRACTION_MODE=fixture` recommended for dry-run |
| API gateway | `:8000` | Proxies `/api/v1/adaptive-tax/**` |
| Frontend | `:5173` | Vite |
| Neo4j Desktop | `:7687` | Optional but preferred for report **MODIFIES** panel |
| Chroma | local persist | Built via `scripts/adaptive_tax_build_chroma.py` (non-empty evidence) |
| Postgres | per `.env` | Required for upload/extract/approve |

```powershell
# Adaptive Tax (:8005) — set explain mode on this process
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_EXTRACTION_MODE = "fixture"
$env:COMP_ADAPTIVE_TAX_EXPLAIN_MODE = "fixture"   # dry-run first
$env:COMP_ADAPTIVE_TAX_KG_MODE = "auto"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005

# Gateway (:8000) — separate terminal
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000

# Frontend (:5173)
cd frontend; npm run dev
```

**B. Dry-run modes**

1. **Fixture explain** (offline): keep `COMP_ADAPTIVE_TAX_EXPLAIN_MODE=fixture`. Run `scripts/adaptive_tax_phase4_demo.py --allow-stub-pdf` once; confirm T2 ≠ T1 and report URLs open.
2. **OpenAI explain** (optional): set `COMP_ADAPTIVE_TAX_EXPLAIN_MODE=openai` + `OPENAI_API_KEY` on the `:8005` process; re-open a report and confirm narrative still respects `sections_cited ⊆ sections_retrieved`.

**C. Screen-record script (UI)**

1. Start screen recorder (OBS / Win+G / etc.).
2. Calculator → reset params if needed (`POST /admin/params/reset-to-pre-amend` or demo script step) → enter **ex04** inputs (salary 3M, QP 2.5M, `param_set=current`) → Calculate → note **T1** → **View report** (calc_id_1).
3. Admin Upload → Act 02/2025 PDF → Extract → Approve (show `param_override` / merge if visible).
4. Calculator → same inputs → Calculate → note **T2 ≠ T1** → **View report** (calc_id_2).
5. On both reports: expand trace; show legal evidence + rule_source quotes (highlight changed Sec 52); show MODIFIES if Neo4j up; show GPT/fixture narrative (or insufficient-evidence empty state honestly).
6. Stop recording. Store the file off-repo; jot the path in [`evaluation/adaptive-tax/README.md`](../evaluation/adaptive-tax/README.md) (Recording path section).

Checklist file (tick boxes): [`evaluation/adaptive-tax/viva_recording_checklist.md`](../evaluation/adaptive-tax/viva_recording_checklist.md).

---

## Phase 1 — Foundation

### What this covers

- Repo layout and shared contracts (see also `docs/PHASE1_STRUCTURE.md`, `docs/language-model_phase1_architecture.md`).
- **Language-model** service skeleton: `backend/comp-language-model/app/` (`/health`, `/ready`).
- Shared traceability schemas: `backend/shared/schemas/traceability.py`.

### Automated tests

> **Important:** Do **not** run `pytest` on `backend/**` and `scripts/` in **one** command.  
> Several services use a top-level package named `app`, which triggers  
> `ImportPathMismatchError` if pytest collects two `app/tests` trees at once.

Run **three** passes from the repo root:

```powershell
# Phase 1b script unit tests (chunking, SQLite, outline helpers)
.\.venv-backend\Scripts\python.exe -m pytest scripts -q --tb=short

# Phase 1 — language-model component
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -q --tb=short

# API gateway (existing monorepo health checks)
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/api-gateway/app/tests -q --tb=short
```

**Expected:** all tests pass (script + language-model + gateway trees separately; language-model may **skip** dense tests without `sentence-transformers`; run `pytest -q` in each tree to confirm counts).

### Run the language-model API locally (optional)

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/comp-language-model --reload --port 8004
```

Then open: `http://127.0.0.1:8004/health` and `http://127.0.0.1:8004/ready`.

---

## Phase 1b — IRD corpus (inventory → manifest → chunks → QA → SQLite)

### What this covers

- **Inventory / download helper:** `scripts/ird_phase1b_bootstrap.py`
- **PDF + HTML → `corpus_v1` JSONL:** `scripts/extract_ir_pdf_text.py`, `scripts/ird_extract_html.py`
- **Batch from manifest:** `scripts/ird_manifest_build_corpus.py`
- **Hash helper:** `scripts/ird_manifest_compute_hashes.py`
- **One-shot pipeline:** `scripts/ird_phase1b_finalize.py`
- **QA markdown:** `scripts/ird_extraction_qa_report.py`
- **SQLite:** `scripts/ird_corpus_sqlite.py`
- **Lex Specialis starter (CSV):** `evaluation/ird/lex_specialis_edges.csv` (refine manually)

### Git / data folders

- `data/raw/` and `data/processed/*` are **gitignored** (large/binary artifacts).
- A **committed snapshot** of the filled manifest lives at:  
  **`evaluation/ird/source_manifest_filled.csv`**  
  Copy it next to your local `data/raw/ird/` copy or pass `--manifest evaluation/ird/source_manifest_filled.csv`.

### Layout (local)

- PDFs (and other raw IRD files): `data/raw/ird/downloads/`
- Filled manifest: `data/raw/ird/source_manifest_filled.csv` (or use `evaluation/ird/` copy)
- Outputs: `data/processed/ird/corpus_v1.jsonl`, `corpus_v1.sqlite`, `extraction_qa_report.md`

### Regenerate manifest template from IRD URL pattern (optional)

```powershell
.\.venv-backend\Scripts\python.exe scripts/ird_write_step2_manifest.py
.\.venv-backend\Scripts\python.exe scripts/ird_manifest_compute_hashes.py `
  --manifest data/raw/ird/source_manifest.csv `
  --files-root data/raw/ird/downloads `
  --out data/raw/ird/source_manifest_filled.csv
```

### Full pipeline (build + QA + SQLite ingest)

```powershell
.\.venv-backend\Scripts\python.exe scripts/ird_phase1b_finalize.py `
  --manifest data/raw/ird/source_manifest_filled.csv `
  --files-root data/raw/ird/downloads `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --sqlite-db data/processed/ird/corpus_v1.sqlite `
  --qa-out data/processed/ird/extraction_qa_report.md `
  --extract-tables `
  --skip-missing
```

**Validate manifest only** (no rebuild):

```powershell
.\.venv-backend\Scripts\python.exe scripts/ird_phase1b_finalize.py `
  --manifest evaluation/ird/source_manifest_filled.csv `
  --files-root data/raw/ird/downloads `
  --skip-build --skip-qa --skip-sqlite
```

### Quick checks after a build

```powershell
# SQLite row counts
.\.venv-backend\Scripts\python.exe scripts/ird_corpus_sqlite.py stats --db data/processed/ird/corpus_v1.sqlite

# Re-run QA report only
.\.venv-backend\Scripts\python.exe scripts/ird_extraction_qa_report.py `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --out data/processed/ird/extraction_qa_report.md
```

### More detail

- IRD folder workflow: `data/raw/ird/README.md`
- Phase 2 handoff notes: `docs/PHASE2_NEXT.md`

---

## Phase 2 — Retrieval baseline, NLU API, benchmarks

**Status:** TF-IDF baseline + `POST /api/v1/nlu/parse` on Component 4; gateway `/api/v1/llm/...` proxy; eval helpers.

**Artifacts:**

- Plan / milestones: `docs/PHASE2_PLAN.md`, `docs/PHASE2_NEXT.md`
- **Task registry (Step 1):** `evaluation/phase2_task_registry.json`
- Benchmark template: `evaluation/benchmark_seed_template.jsonl` (each row: `task_id`, gold fields per registry)

### Environment (optional corpus)

In repo root `.env` (or shell):

```text
COMP_LLM_CORPUS_JSONL=data/processed/ird/corpus_v1.jsonl
COMP_LLM_RETRIEVAL_BACKEND=tfidf
COMP_LLM_RETRIEVAL_TOP_K=8
COMP_LLM_INTENT_BENCHMARK_JSONL=evaluation/benchmark_seed_template.jsonl
```

For **dense** retrieval on the API (Step 12), set `COMP_LLM_RETRIEVAL_BACKEND=dense`, install `backend/requirements-retrieval-dense.txt`, and optionally `COMP_LLM_DENSE_MODEL` / `COMP_LLM_DENSE_DEVICE`. Response `model` is `dense-baseline` when the index loads.

If corpus path is unset or missing, NLU parse uses `stub-no-corpus` for retrieval (empty `retrieval_hits`). If the intent benchmark path is unset or missing, `predicted_intent` is null. If `backend=dense` but dependencies are missing, the index does not load and behavior matches no corpus.

### Run Component 4 with corpus (port 8004)

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
$env:COMP_LLM_CORPUS_JSONL = "data/processed/ird/corpus_v1.jsonl"
$env:COMP_LLM_INTENT_BENCHMARK_JSONL = "evaluation/benchmark_seed_template.jsonl"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

**NLU parse (direct):**

```powershell
curl -s -X POST http://127.0.0.1:8004/api/v1/nlu/parse -H "Content-Type: application/json" -d "{\"utterance\":\"What is personal relief?\"}"
```

**Through API gateway** (start gateway + LM; gateway default `COMP_LLM_URL=http://localhost:8004`):

```powershell
curl -s -X POST http://127.0.0.1:8000/api/v1/llm/nlu/parse -H "Content-Type: application/json" -d "{\"utterance\":\"What is personal relief?\"}"
```

`GET /ready` on the gateway includes a `language_model` probe.

**Response (Phase 2 Step 4):** JSON includes `predicted_intent` and `intent_model` when `COMP_LLM_INTENT_BENCHMARK_JSONL` loads; `intent` echoes optional request `intent_hint`.

### Validate benchmark (Phase 2 task shape + gold chunk IDs in corpus)

```powershell
.\.venv-backend\Scripts\python.exe scripts/validate_benchmark_corpus.py `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl
```

Use `--skip-task-shape` if you only want chunk-ID membership checks. Override the registry with `--task-registry PATH`.

### TF-IDF recall@k (any gold in top-k)

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_retrieval_tfidf.py `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --k 8
```

### TF-IDF intent baseline (Phase 2 Step 2)

Scores rows with `task_id` `intent_classification` or `joint_nlu_retrieval` (gold intent from `gold_intent` or `intent`). Default is leave-one-out CV:

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_intent_tfidf.py `
  --benchmark evaluation/benchmark_seed_template.jsonl
```

Holdout split and per-example JSON:

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_intent_tfidf.py `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --mode holdout --test-fraction 0.3 --seed 1 --per-example
```

### Joint success — intent ∧ retrieval@k (Phase 2 Step 3)

Only **`joint_nlu_retrieval`** rows (must have gold intent + `gold_chunk_ids`). Intent model uses the same pool as Step 2 (LOOCV excludes the current example).

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_joint_tfidf.py `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --k 8 --per-example
```

### Phase 2 Step 5 — One-shot experiment record (append JSONL)

Runs retrieval + intent + joint evals and appends **one JSON line** to `evaluation/phase2_runs.jsonl` (creates file if needed). Use `--dry-run` to print without appending.

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_experiment_run.py `
  --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --k 8 `
  --model-version tfidf_baseline_2026_05_11 `
  --notes "weekly smoke"
```

Options: `--skip-retrieval`, `--skip-intent`, `--skip-joint`, `--append PATH`, `--intent-mode holdout`, `--joint-mode holdout`, etc.

Schema reference: `evaluation/experiment_run_template.json` (Phase 2 fills `metrics.phase2_*` and `phase2_eval_outputs`).

### Phase 2 M5 — Gate (frozen baseline)

**Decision:** The Phase 2 **shipping baseline** is **TF-IDF passage retrieval** over `corpus_v1` plus **TF-IDF centroid intent** (optional via `COMP_LLM_INTENT_BENCHMARK_JSONL`). Dense encoders / RAG answers are **future candidates** and must be promoted via new `phase2_runs.jsonl` entries and an updated gate file.

| Artifact | Purpose |
|----------|---------|
| [`evaluation/frozen/phase2_M5_baseline.json`](../evaluation/frozen/phase2_M5_baseline.json) | Machine-readable gate: baseline name, env vars, promotion rule |
| [`evaluation/frozen/nlu_parse_request.schema.json`](../evaluation/frozen/nlu_parse_request.schema.json) | Frozen `POST /api/v1/nlu/parse` request JSON |
| [`evaluation/frozen/nlu_parse_response.schema.json`](../evaluation/frozen/nlu_parse_response.schema.json) | Frozen parse response JSON |

**Regression smoke:** **`scripts/phase2_regression_smoke.py`** (Step 7) on committed fixtures; locally you can still run Step 5 `--dry-run` on real data and compare `phase2_runs.jsonl`.

**Contract tests:** `backend/comp-language-model/app/tests/test_m5_frozen_contract.py`.

### Phase 2 Step 6 — Leaderboard from `phase2_runs.jsonl`

After appending runs with Step 5, summarize candidates (quality, latency, cost):

```powershell
# Markdown table (default); skip runs that have phase2_errors
.\.venv-backend\Scripts\python.exe scripts/phase2_leaderboard.py --input evaluation/phase2_runs.jsonl

.\.venv-backend\Scripts\python.exe scripts/phase2_leaderboard.py --format json --sort retrieval
.\.venv-backend\Scripts\python.exe scripts/phase2_leaderboard.py --format csv --sort latency
```

Flags: `--include-errors`, `--sort joint|retrieval|intent|latency`.

### Phase 2 Step 7 — Regression smoke (fixtures + CI)

Validates benchmark ↔ corpus rules and runs the full **experiment bundle** on **committed** tiny fixtures (no `data/processed` required):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_regression_smoke.py
```

Fixtures: `evaluation/fixtures/phase2_smoke/`. On GitHub, workflow **Phase 2 smoke** (`.github/workflows/phase2-smoke.yml`) runs the same script after `pip install -r backend/requirements.txt`.

### Phase 2 Step 8 — Handoff Markdown report

Generates one file with M5 baseline, task table, leaderboard, schema paths, and commands (for thesis chapter / examiner pack):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_export_handoff.py
# default: evaluation/phase2_handoff/REPORT.md

.\.venv-backend\Scripts\python.exe scripts/phase2_export_handoff.py --stdout
.\.venv-backend\Scripts\python.exe scripts/phase2_export_handoff.py --runs evaluation/phase2_runs.jsonl --out docs/phase2_handoff_snapshot.md
```

### Phase 2 Step 9 — Benchmark train / dev / test splits

Create three JSONLs for held-out evaluation (`benchmark_train.jsonl`, `benchmark_dev.jsonl`, `benchmark_test.jsonl`):

**A. Deterministic split from `example_id`** (70% / 15% / 15% by default; change with `--train-fraction` / `--dev-fraction`; test is remainder):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_split_benchmark.py `
  --benchmark evaluation/benchmark_seed_template.jsonl `
  --out-dir evaluation/splits/my_run `
  --strategy hash `
  --train-fraction 0.7 --dev-fraction 0.15 --seed my_project_v1
```

**B. Expert-assigned `split` on each row** (`train` / `dev` / `test`; `val` / `validation` → `dev`). Fails if any row is missing it:

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_split_benchmark.py `
  --benchmark evaluation/benchmark_v1_dev.jsonl `
  --out-dir evaluation/splits/my_run `
  --strategy explicit
```

Use `--prefix mybench` to emit `mybench_train.jsonl`, etc. Every output line includes a normalized `split` field.

### Phase 2 Step 10 — Held-out eval (fit intent on train split only)

After Step 9, point **intent** and **joint** at `benchmark_train.jsonl` for fitting and at your **eval** file (e.g. merged `benchmark_dev.jsonl` + `benchmark_test.jsonl`) for scoring. Retrieval metrics always use the **eval** `--benchmark` only.

**Merge dev + test into one eval JSONL (Step 13):**

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_merge_benchmark_splits.py `
  --inputs evaluation/splits/my_run/benchmark_dev.jsonl evaluation/splits/my_run/benchmark_test.jsonl `
  -o evaluation/splits/my_run/benchmark_eval_merged.jsonl
```

Use `--dedupe-example-id` if the same `example_id` could appear in more than one input (first file wins).

**Intent:**

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_intent_tfidf.py `
  --train-benchmark evaluation/splits/my_run/benchmark_train.jsonl `
  --benchmark evaluation/splits/my_run/benchmark_eval_merged.jsonl `
  --task-registry evaluation/phase2_task_registry.json
```

**Joint** (same train/eval split; `--corpus-jsonl` unchanged):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_joint_tfidf.py `
  --corpus-jsonl data/processed/corpus_v1.jsonl `
  --intent-train-benchmark evaluation/splits/my_run/benchmark_train.jsonl `
  --benchmark evaluation/splits/my_run/benchmark_eval_merged.jsonl `
  --k 8 `
  --task-registry evaluation/phase2_task_registry.json
```

**Full experiment record** (retrieval + intent + joint):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_experiment_run.py `
  --corpus-jsonl data/processed/corpus_v1.jsonl `
  --train-benchmark evaluation/splits/my_run/benchmark_train.jsonl `
  --benchmark evaluation/splits/my_run/benchmark_eval_merged.jsonl `
  --k 8 `
  --model-version tfidf_held_out_v1
```

Intent and joint eval JSON use `"mode": "held_out_train_split"`; the experiment record sets `dataset.split` to `held_out_train_eval`.

### Phase 2 Step 11 — Dense retrieval (sentence-transformers)

Install optional deps (adds PyTorch):

```powershell
pip install -r backend/requirements-retrieval-dense.txt
```

**Standalone retrieval eval** (default model `sentence-transformers/all-MiniLM-L6-v2`):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_eval_retrieval_dense.py `
  --corpus-jsonl data/processed/corpus_v1.jsonl `
  --benchmark evaluation/benchmark_v1_dev.jsonl `
  --k 8 `
  --model-name sentence-transformers/all-MiniLM-L6-v2
```

**Experiment bundle** (dense retrieval + dense-backed joint; intent still TF-IDF centroid):

```powershell
.\.venv-backend\Scripts\python.exe scripts/phase2_experiment_run.py `
  --corpus-jsonl data/processed/corpus_v1.jsonl `
  --benchmark evaluation/benchmark_v1_dev.jsonl `
  --retrieval-backend dense `
  --dense-model sentence-transformers/all-MiniLM-L6-v2 `
  --model-version minilm_dense_v1
```

### Phase 2 Step 12 — API: dense retrieval on `POST /api/v1/nlu/parse`

Parity with Step 11 offline eval: the language-model service loads **`DenseChunkIndex`** when `COMP_LLM_RETRIEVAL_BACKEND=dense` (same default model id as the scripts). Intent remains the TF-IDF centroid from `COMP_LLM_INTENT_BENCHMARK_JSONL`.

**Example `.env`:**

```text
COMP_LLM_CORPUS_JSONL=data/processed/ird/corpus_v1.jsonl
COMP_LLM_RETRIEVAL_BACKEND=dense
COMP_LLM_DENSE_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Frozen response schema allows `model`: **`dense-baseline`** (see `evaluation/frozen/nlu_parse_response.schema.json`).

### Phase 2 Step 13 — Retrieval MRR@k + merge split JSONLs

- **MRR:** Retrieval eval JSON (`phase2_eval_retrieval_tfidf.py`, `phase2_eval_retrieval_dense.py`) includes **`mrr`**: mean reciprocal rank of the first gold chunk in the top-k list. The experiment bundle stores **`metrics.phase2_retrieval_mrr_at_k`**; **`phase2_leaderboard.py`** adds a **`retrieval_mrr`** column.
- **Merge:** `scripts/phase2_merge_benchmark_splits.py` — see Step 10 above.

### Phase 2 Step 14 — Law-grounded query with citations (`POST /api/v1/query`)

Returns **retrieval hits** plus **truncated chunk text** from the same corpus JSONL as the index. No generative answer in this step — citations only.

**Direct (language-model on port 8004):**

```powershell
curl -s -X POST http://127.0.0.1:8004/api/v1/query -H "Content-Type: application/json" -d "{\"question\":\"What is personal relief?\",\"top_k\":5}"
```

**Via gateway:**

```powershell
curl -s -X POST http://127.0.0.1:8000/api/v1/llm/query -H "Content-Type: application/json" -d "{\"question\":\"What is personal relief?\"}"
```

Optional env: **`COMP_LLM_QUERY_CITATION_MAX_CHARS`** (default 2000). Frozen schemas: `evaluation/frozen/query_request.schema.json`, `query_response.schema.json`.

**Future:** cross-encoder reranking, learned intent encoders, generative answer with citations, full model zoo.

---

## Phase 3+ — Knowledge graph, GraphRAG, reasoning

### Phase 3 Step 1 — Ontology sketch (node labels)

**Status:** `knowledge_graph/ontology_v1.json` lists **eight** node kinds for KG v1, with `id_property`, `key_properties`, and notes mapping to `corpus_v1` / manifest fields (`source_doc_id`, `chunk_id`, `section_ref`, etc.).

### Phase 3 Step 2 — Relationship types (frozen)

**Status:** `ontology_v1.json` (**1.2.0**, `phase` **3a-step10**) defines Neo4j relationship types in UPPER_SNAKE (original eleven + Step 10 **VIEW_**\* edges), with allowed source/target node labels. Types marked `lex_specialis_relevant` are intended for precedence logic in Step 3c (`MODIFIES`, `SUPERSEDES`, `OVERRIDES`).

**Validate:**

```powershell
Set-Location d:\research\R26-DS-004
python -m pytest scripts/test_kg_ontology_v1.py -q
```

**Load in Python:** `scripts/kg_ontology_lib.py` → `load_ontology()`, `validate_ontology()`.

### Phase 3 Step 3 — Normalize chunk metadata for loading

**Status:** `knowledge_graph/chunk_metadata_kg_v1.json` documents the contract. `scripts/ird_corpus_lib.py` adds `normalize_chunk_for_kg()` (`effective_from` ← `effective_start_date`, `section_label` ← `section_ref` or outline tail) and `validate_kg_chunk_metadata()`.

**CLI:**

```powershell
Set-Location d:\research\R26-DS-004
py -3 scripts/validate_corpus_kg_metadata.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl
py -3 scripts/validate_corpus_kg_metadata.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --strict-doc-meta
```

**Tests:** `py -3 -m pytest scripts/test_kg_corpus_metadata.py -q`

### Phase 3 Step 4 — ETL pipeline (chunk → graph)

**Status:** `knowledge_graph/etl_chunk_to_graph_v1.json` describes the pilot mapping. Each corpus row → MERGE plan: **LawInstrument** + **TextChunk**; optional **Section** when `section_label` exists; edges **HAS_CHUNK** (from Section or LawInstrument) and **PART_OF** (Section → LawInstrument). Proof Map rule: every row yields exactly one **TextChunk** node keyed by `chunk_id`.

**Preview bundles:**

```powershell
Set-Location d:\research\R26-DS-004
py -3 scripts/export_kg_etl_preview.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --limit 3 --no-text
```

**Tests:** `py -3 -m pytest scripts/test_kg_etl.py -q`

### Phase 3 Step 5 — Neo4j constraints and indexes

**Status:** `knowledge_graph/neo4j/00_constraints.cypher` (8 uniqueness constraints) and `01_range_indexes.cypher` (filter indexes). Neo4j **5+** syntax. Optional driver: `pip install -r knowledge_graph/requirements-neo4j.txt`.

**cypher-shell (from `knowledge_graph/neo4j/`):**

```powershell
cypher-shell -a neo4j://127.0.0.1:7687 -u neo4j -p "<password>" -f 00_constraints.cypher
cypher-shell -a neo4j://127.0.0.1:7687 -u neo4j -p "<password>" -f 01_range_indexes.cypher
```

**Python:** `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` → `py -3 scripts/neo4j_apply_schema.py`

**Tests (no DB):** `py -3 -m pytest scripts/test_neo4j_schema_files.py -q`

### Phase 3 Step 6 — Load nodes in safe order

**Status:** `scripts/neo4j_load_corpus_chunks.py` streams `corpus_v1.jsonl`, validates KG metadata, builds Step 4 bundles, and **MERGE**s in order: **LawInstrument** → **Section** (when `section_uid` exists) → **TextChunk**, then relationships. One **write transaction per row** (idempotent). Apply **Step 5** schema first.

**Examples:**

```powershell
Set-Location d:\research\R26-DS-004
pip install -r knowledge_graph/requirements-neo4j.txt
$env:NEO4J_URI = "neo4j://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<password>"
py -3 scripts/neo4j_load_corpus_chunks.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --dry-run --limit 10
py -3 scripts/neo4j_load_corpus_chunks.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --strict-doc-meta --no-text
```

**Tests:** `py -3 -m pytest scripts/test_kg_bundle_merge_order.py scripts/test_kg_etl.py -q`

### Phase 3 Step 7 — Load edges (parsing + manual curation)

**Status:** Curated edges as **JSONL** (`edge_ingest_v1.json`). Each row validated against **`ontology_v1.json`** (allowed rel type, endpoint labels, correct `from_key` / `to_key`). Relationship properties limited to **`optional_edge_properties`** (e.g. `confidence`, `review_status`, `source_note`) so uncertain automation is explicit.

**Heuristic automation:** substring alias match → **MENTIONS** rows with `review_status: auto_alias_match`.

```powershell
Set-Location d:\research\R26-DS-004
py -3 scripts/export_heuristic_mentions_edges.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl `
  --concepts-json knowledge_graph/examples/concepts_seed.json --out build/mentions_heuristic.jsonl --limit-chunks 100
py -3 scripts/neo4j_load_curated_edges.py --edges-jsonl build/mentions_heuristic.jsonl --dry-run
py -3 scripts/neo4j_load_curated_edges.py --edges-jsonl knowledge_graph/examples/curated_edges_sample.jsonl --warn-miss
```

**Ontology helpers:** `kg_ontology_lib.node_id_property()`, `relationship_spec()`.

**Tests:** `py -3 -m pytest scripts/test_kg_curated_edges.py -q`

### Phase 3 Step 8 — Lex Specialis metadata

**Status:** `knowledge_graph/lex_specialis_v1.json` defines **authority classes**, default **authority_weight_numeric** and **specificity_rank**, **precedence_order** for tie-breaks, and a **section_specificity_bonus**. `kg_lex_specialis_lib.py` infers `authority_class` from `tier`, `instrument_type`, `doc_type`, `is_draft` (draft guides demoted; Tier A default **statute**; Tier C **hub_summary**). **ETL bundles** (v1.1.0) attach Lex fields to **LawInstrument**, **Section**, and **TextChunk**. Neo4j: `02_lex_indexes.cypher` (re-apply `scripts/neo4j_apply_schema.py` after pulling this file).

**Tests:** `py -3 -m pytest scripts/test_kg_lex_specialis.py scripts/test_kg_etl.py scripts/test_neo4j_schema_files.py -q`

### Phase 3 Step 9 — Override paths

**Status:** Explicit **“new beats old”** encoding via **`OVERRIDES`** (Section→Section), **`MODIFIES`** (LawInstrument→Section), **`SUPERSEDES`** (LawInstrument→LawInstrument). Documented in **`knowledge_graph/lex_override_paths_v1.json`** (edge direction, recommended rel properties, fallback to node `specificity_rank` / `lex_effective_*` when edges are absent). Ingest with the same JSONL as Step 7; loader flag **`--strict-lex-overrides`** requires **`source_note`** and **`review_status`** on those three rel types.

```powershell
py -3 scripts/neo4j_load_curated_edges.py --edges-jsonl knowledge_graph/examples/override_edges_sample.jsonl --dry-run --strict-lex-overrides
```

**Tests:** `py -3 -m pytest scripts/test_kg_override_edges.py -q`

### Phase 3 Step 10 — Consolidated-text view (optional)

**Status:** **Ontology 1.2.0** adds **ConsolidatedViewPassage** (`anchor_id`) plus **VIEW_IN_INSTRUMENT**, **VIEW_TRACES_TO_SECTION**, **VIEW_TRACES_TO_INSTRUMENT** so consolidated PDF wording can point to underlying **Section** / **LawInstrument** nodes. Re-run **`scripts/neo4j_apply_schema.py`** for constraint **#9** and **`03_consolidated_view_indexes.cypher`**. Ingest anchors with **`neo4j_load_consolidated_anchors.py`**; load trace edges with **`neo4j_load_curated_edges.py`** (same JSONL contract as Step 7).

```powershell
py -3 scripts/neo4j_load_consolidated_anchors.py --anchors-jsonl knowledge_graph/examples/consolidated_view_anchor_rows.jsonl --dry-run
py -3 scripts/neo4j_load_curated_edges.py --edges-jsonl knowledge_graph/examples/consolidated_view_trace_edges_sample.jsonl --dry-run --strict-lex-overrides
```

**Tests:** `py -3 -m pytest scripts/test_kg_consolidated_view.py scripts/test_kg_ontology_v1.py scripts/test_neo4j_schema_files.py -q`

### Phase 3 Step 11 — NLU entity type → graph mapping

**Status:** `knowledge_graph/nlu_entity_graph_map_v1.json` lists canonical **entity slot** names (e.g. `relief_type`, `income_category`, `assessment_year`) with **target Neo4j label** (or `null` for metadata-only), **match strategy** (`property_exact_ci`, `concept_alias_ci`, `section_uid_from_context`, `metadata_only`), and **fallback** (`clarify`, `skip`, `nearest_concept`). Validated against **`ontology_v1.json`** labels via `kg_nlu_entity_map_lib.validate_entity_map()`.

**Tests:** `py -3 -m pytest scripts/test_kg_nlu_entity_map.py -q`

### Phase 3 Step 12 — NLU intent → graph entry pattern

**Status:** `knowledge_graph/nlu_intent_graph_map_v1.json` maps each **`nlu_intent`** (e.g. `personal_relief`, `residence_scope`, `donation_relief`) to an **`entry`** block: **`strategy`** (`match_concept_by_id`, `match_relief_by_id`, `retrieval_first`, `cypher_template`), **`parameters`**, and a **`cypher_template`** starter query with **`$parameter`** placeholders. Includes **`_default`** for unknown intents. Validator checks placeholder coverage; **`expansion_hints`** are non-executable documentation for Phase 4.

**Tests:** `py -3 -m pytest scripts/test_kg_nlu_intent_map.py -q`

### Phase 3 Step 13 — Node-linked embeddings (artifact outside Neo4j)

**Status:** Dense vectors are keyed to graph nodes via **`(neo4j_label, id_property, node_id)`** (pilot: **TextChunk** / **`chunk_id`**). Layout is documented in **`knowledge_graph/node_embeddings_v1.json`**: per-run directory with **`node_embeddings_meta.json`** plus a compressed **`.npz`** (`embeddings` + `chunk_ids` parallel arrays). **`scripts/kg_node_embeddings_lib.py`** validates metadata, writes/loads bundles; **`scripts/compute_node_embeddings_bundle.py`** builds from the same JSONL corpus as dense retrieval (requires **`sentence-transformers`** — see **`backend/requirements-retrieval-dense.txt`**). Use **`--dry-run`** to count rows and emit **`vector_storage.format: pending`** only.

```powershell
# Dry-run (no model): pending manifest + row count
py -3 scripts/compute_node_embeddings_bundle.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --out-dir knowledge_graph/embeddings --embedding-run-id my_run_1 --dry-run

# Full run: ensure comp-language-model deps (same PYTHONPATH pattern as other LM scripts)
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
py -3 scripts/compute_node_embeddings_bundle.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl --out-dir knowledge_graph/embeddings --embedding-run-id my_run_1
```

**Tests:** `py -3 -m pytest scripts/test_kg_node_embeddings.py -q`

### Phase 3 Step 14 — API: load dense vectors from Step 13 bundle

**Status:** When **`COMP_LLM_RETRIEVAL_BACKEND=dense`**, optional **`COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR`** points at a directory containing **`node_embeddings_meta.json`** + **`.npz`** (same layout as Step 13). The language-model service loads **precomputed** passage embeddings from disk and only runs the encoder for **queries** (faster startup, smaller RAM vs full corpus encode). **`COMP_LLM_CORPUS_JSONL`** must still be set so **`POST /api/v1/query`** and NLU can resolve **citation excerpts**. If the bundle path is missing or invalid, startup **falls back** to encoding from JSONL. **`COMP_LLM_DENSE_MODEL`** should match the bundle’s **`embedding_model_id`** (a warning is logged if they differ).

```powershell
$env:COMP_LLM_CORPUS_JSONL = "data/processed/ird/corpus_v1.jsonl"
$env:COMP_LLM_RETRIEVAL_BACKEND = "dense"
$env:COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR = "knowledge_graph/embeddings/my_run_1"
```

**Tests:** `py -3 -m pytest backend/comp-language-model/app/tests/test_dense_embedding_bundle.py -q` (from repo root; `PYTHONPATH` must include repo root and `backend/comp-language-model` — see NLU test section above).

### Phase 3 Step 15 — Retrieval hits / citations: KG join metadata from corpus

**Status:** **`POST /api/v1/nlu/parse`** **`retrieval_hits`** and **`POST /api/v1/query`** **`citations`** include optional **Phase 3** fields when the corpus row provides them: **`source_doc_id`**, **`section_uid`** (same formula as **`kg_etl_lib.make_section_uid`** on **`normalize_chunk_for_kg`**), **`section_label`**, **`tier`**, **`instrument_type`**, **`content_kind`**. Loaded at startup via **`app/services/corpus_chunk_kg_join.py`** into **`app.state.chunk_kg_join_by_id`**. Frozen NLU/query response schemas and **`phase2_M5_baseline.json`** **`gate_id`** updated accordingly.

**Tests:** `py -3 -m pytest backend/comp-language-model/app/tests/test_corpus_chunk_kg_join.py backend/comp-language-model/app/tests/test_query.py -q` (plus full `app/tests` tree as usual).

Suggested future headings:

- Phase 3 — Tax KG + Neo4j (or chosen store)
- Phase 4 — Retrieval / GraphRAG
- Phase 5 — Symbolic / Think-Twice
- Phase 6 — Proof map / UI

---

## Troubleshooting

| Symptom | What to do |
|--------|------------|
| `ImportPathMismatchError` / duplicate `app` in pytest | Run pytest **per** `scripts/`, `comp-language-model`, `api-gateway` as above. |
| `ModuleNotFoundError: app` when running LM tests | Set `PYTHONPATH` to include `backend/comp-language-model` **and** repo root. |
| `pdfplumber` / hash / crawl errors | `pip install -r backend/requirements.txt`; check network for IRD crawl. |
| Manifest “missing file” | Ensure `file_name` in CSV **exactly** matches files under `data/raw/ird/downloads/`. |

---

## Changelog (maintain when phases advance)

| Date | Change |
|------|--------|
| 2026-08-03 | Adaptive Tax Phase 4 Step 8: viva recording checklist in runbook + `evaluation/adaptive-tax/viva_recording_checklist.md` (path note in eval README). |
| 2026-08-03 | Adaptive Tax Phase 4 Step 7: `evaluation/adaptive-tax/` scorers + filled `metrics_table.md` (Chapter 4). |
| 2026-08-03 | Adaptive Tax Phase 4 Step 6: `scripts/adaptive_tax_phase4_demo.py` + runbook viva copy-paste (T1≠T2, explain both calc ids, report URLs). |
| 2026-08-03 | Adaptive Tax Phase 4 Step 5: report UI `/adaptive-tax/report/:calcId` (trace, evidence, MODIFIES, narrative); calculator View report link. |
| 2026-08-03 | Adaptive Tax Phase 4 Step 4: `POST /api/v1/explain` (fixture\|openai), citation faithfulness filter, explain_ex04_sample fixture. |
| 2026-08-03 | Adaptive Tax Phase 4 Step 3: evidence gatherer (`section_uid`→Chroma/PG/MODIFIES → EvidenceBundle). |
| 2026-08-03 | Adaptive Tax Phase 4 Step 2: runtime Sec 52 param override on approve; `POST /admin/params/reset-to-pre-amend`; T1≠T2 with ex04 inputs. |
| 2026-08-03 | Adaptive Tax Phase 4 Step 1: calc JSON store + `calc_id` on `POST /calculate`, `GET /api/v1/calculations/{calc_id}`. |
| 2026-08-03 | Adaptive Tax Phase 4 Step 0: explain/calc-store/param-override env knobs in `config.py` + `.env.example`; runbook Phase 4 stub; README status. |
| 2026-08-03 | Adaptive Tax Phase 3: pure-Python rule engine + `POST /api/v1/calculate`, file/Neo4j KG client, ex01–ex08 fixtures, calculator UI `/adaptive-tax/calculator`. |
| 2026-08-02 | Adaptive Tax Phase 2 Step E: approve→Neo4j MODIFIES + Relief update + Chroma re-index; `/knowledge/graph-stats` + `/knowledge/rag/search`. |
| 2026-08-02 | Adaptive Tax Phase 2 Step 0b: Neo4j Desktop + embedded Chroma env (`NEO4J_*`, `CHROMA_*`, corpus path); optional docker profile `adaptive-tax`. |
| 2026-08-02 | Adaptive Tax Phase 1: amendment upload/extract/review API + admin UI; Alembic tables; fixture/OpenAI extract; approve→`rule_versions` (graph merge stubbed). |
| 2026-08-02 | Adaptive Tax Phase 0 scaffold: `comp-adaptive-tax` on :8005, gateway `/api/v1/adaptive-tax`, frontend `/adaptive-tax/home`. |
| 2026-05-10 | Initial runbook: Phase 1 tests, Phase 1b pipeline, Phase 2 stub. |
| 2026-05-10 | Added “Dashboard — frontend + backends” (Vite + gateway + ports 8002/8003). |
| 2026-05-11 | Phase 2 Step 1: `evaluation/phase2_task_registry.json`, stricter benchmark validation, eval by task. |
| 2026-05-11 | Phase 2 Step 2: TF-IDF intent centroid baseline + `phase2_eval_intent_tfidf.py`. |
| 2026-05-11 | Phase 2 Step 3: `phase2_eval_joint_tfidf.py` (`joint_success`). |
| 2026-05-11 | Phase 2 Step 4: `COMP_LLM_INTENT_BENCHMARK_JSONL`, `predicted_intent` on NLU parse. |
| 2026-05-11 | Phase 2 Step 5: `phase2_experiment_run.py`, `phase2_runs.jsonl`, template metrics keys. |
| 2026-05-11 | Phase 2 **M5 gate**: `evaluation/frozen/phase2_M5_baseline.json`, NLU JSON Schemas, contract tests. |
| 2026-05-11 | Phase 2 **Step 6**: `phase2_leaderboard.py` (report from `phase2_runs.jsonl`). |
| 2026-05-11 | Phase 2 **Step 7**: `phase2_regression_smoke.py`, `evaluation/fixtures/phase2_smoke/`, GitHub Action. |
| 2026-05-11 | Phase 2 **Step 8**: `phase2_export_handoff.py` → `evaluation/phase2_handoff/REPORT.md`. |
| 2026-05-11 | Phase 2 **Step 9**: `phase2_split_benchmark.py` (train/dev/test JSONL). |
| 2026-05-11 | Phase 2 **Step 10**: held-out train/eval flags on intent, joint, and `phase2_experiment_run.py`. |
| 2026-05-11 | Phase 2 **Step 11**: `dense_chunk_index.py`, `phase2_eval_retrieval_dense.py`, bundle `--retrieval-backend dense`. |
| 2026-05-11 | Phase 2 **Step 12**: `COMP_LLM_RETRIEVAL_BACKEND`, NLU parse `dense-baseline`, `attach_retrieval_index`. |
| 2026-05-11 | Phase 2 **Step 13**: retrieval **`mrr`**, `phase2_merge_benchmark_splits.py`, leaderboard MRR column. |
| 2026-05-11 | Phase 2 **Step 14**: `POST /api/v1/query`, citation excerpts, frozen query schemas. |
| 2026-05-12 | Phase 3 **Step 1**: `knowledge_graph/ontology_v1.json`, `scripts/kg_ontology_lib.py`, `scripts/test_kg_ontology_v1.py`. |
| 2026-05-12 | Phase 3 **Step 2**: ontology **1.1.0** — `relationship_types` + rel validation in `kg_ontology_lib.py`. |
| 2026-05-12 | Phase 3 **Step 3**: `chunk_metadata_kg_v1.json`, `normalize_chunk_for_kg` / `validate_kg_chunk_metadata`, `validate_corpus_kg_metadata.py`. |
| 2026-05-12 | Phase 3 **Step 4**: `etl_chunk_to_graph_v1.json`, `kg_etl_lib.py`, `export_kg_etl_preview.py`, `test_kg_etl.py`. |
| 2026-05-12 | Phase 3 **Step 5**: `knowledge_graph/neo4j/*.cypher`, `neo4j_apply_schema.py`, `requirements-neo4j.txt`, `test_neo4j_schema_files.py`. |
| 2026-05-12 | Phase 3 **Step 6**: `neo4j_load_corpus_chunks.py`, `bundle_nodes_merge_order`, `test_kg_bundle_merge_order.py`. |
| 2026-05-12 | Phase 3 **Step 7**: `edge_ingest_v1.json`, `kg_curated_edges_lib.py`, `neo4j_load_curated_edges.py`, heuristic MENTIONS export, `test_kg_curated_edges.py`. |
| 2026-05-12 | Phase 3 **Step 8**: `lex_specialis_v1.json`, `kg_lex_specialis_lib.py`, ETL **1.1.0**, `neo4j/02_lex_indexes.cypher`, `test_kg_lex_specialis.py`. |
| 2026-05-12 | Phase 3 **Step 9**: `lex_override_paths_v1.json`, `kg_override_edges_lib.py`, `override_edges_sample.jsonl`, `--strict-lex-overrides`, `test_kg_override_edges.py`. |
| 2026-05-12 | Phase 3 **Step 10**: ontology **1.2.0** ConsolidatedViewPassage + VIEW_* rels, `consolidated_view_v1.json`, `kg_consolidated_view_lib.py`, `neo4j_load_consolidated_anchors.py`, `03_consolidated_view_indexes.cypher`. |
| 2026-05-12 | Phase 3 **Step 11**: `nlu_entity_graph_map_v1.json`, `kg_nlu_entity_map_lib.py`, `test_kg_nlu_entity_map.py`. |
| 2026-05-12 | Phase 3 **Step 12**: `nlu_intent_graph_map_v1.json`, `kg_nlu_intent_map_lib.py`, `test_kg_nlu_intent_map.py`. |
| 2026-05-12 | Phase 3 **Step 13**: `node_embeddings_v1.json`, `kg_node_embeddings_lib.py`, `compute_node_embeddings_bundle.py`, `DenseChunkIndex` export accessors, `test_kg_node_embeddings.py`. |
| 2026-05-12 | Phase 3 **Step 14**: `COMP_LLM_DENSE_EMBEDDING_BUNDLE_DIR`, `node_embedding_bundle.py`, `DenseChunkIndex.from_embedding_bundle_dir`, `test_dense_embedding_bundle.py`. |
| 2026-05-12 | Phase 3 **Step 15**: `corpus_chunk_kg_join.py`, optional KG fields on `RetrievalHit` / `Citation`, frozen schema + M5 `gate_id` bump, `test_corpus_chunk_kg_join.py`. |

*(Append a row each time you materially update commands for a new phase.)*
