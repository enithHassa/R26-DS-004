# Component C — Run & Test Guide

**Service:** Intelligent Tax Advisory Language Model  
**Path:** `backend/comp-language-model`  
**Default port:** `8004`  
**Gateway prefix:** `/api/v1/llm/` → proxies to this service

Step-by-step instructions to **set up**, **run**, and **test** your component on Windows (PowerShell). All commands assume you start from the **repository root**: `d:\research\R26-DS-004`.

For the big-picture overview see [`component-c-language-model-guide.md`](component-c-language-model-guide.md).  
For the completion checklist see [`component-c-completion-todo.md`](component-c-completion-todo.md).

---

## 1. Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Node.js (frontend only) | 20 LTS+ |
| Git | any recent |

Optional (for full features):

- **Neo4j** 5+ — knowledge graph enrichment
- **Gemini API key** — plain-language answer synthesis
- **sentence-transformers** — dense retrieval (`backend/requirements-retrieval-dense.txt`)

---

## 2. One-time setup

### 2.1 Backend virtual environment

```powershell
cd d:\research\R26-DS-004

python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r backend\requirements.txt
```

Optional dense retrieval:

```powershell
pip install -r backend\requirements-retrieval-dense.txt
```

### 2.2 Environment file

```powershell
copy .env.example .env
```

Edit `.env` and set at minimum:

```text
COMP_LLM_URL=http://localhost:8004
COMP_LLM_CORPUS_JSONL=data/processed/ird/corpus_v1.jsonl
COMP_LLM_INTENT_BENCHMARK_JSONL=evaluation/benchmark_seed_template.jsonl
```

Optional (recommended for demos):

```text
COMP_LLM_GRAPH_ENABLED=true
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-neo4j-password>

COMP_LLM_ANSWER_SYNTHESIS_ENABLED=true
COMP_LLM_GEMINI_API_KEY=<your-gemini-key>
COMP_LLM_GEMINI_MODEL=gemini-2.0-flash

COMP_LLM_LEX_SPECIALIS_RERANK=true
COMP_LLM_THINK_TWICE_ENABLED=true
COMP_LLM_PROOF_MAP_ENABLED=true
```

Phase 5/6 flags are **on by default** in code; set to `false` only if you want citations without Proof Map or validation.

### 2.3 Build the legal corpus (if missing)

Large files live under `data/` (gitignored). If `data/processed/ird/corpus_v1.jsonl` does not exist:

```powershell
.\.venv-backend\Scripts\python.exe scripts\ird_phase1b_finalize.py `
  --manifest evaluation\ird\source_manifest_filled.csv `
  --files-root data\raw\ird\downloads `
  --corpus-jsonl data\processed\ird\corpus_v1.jsonl `
  --sqlite-db data\processed\ird\corpus_v1.sqlite `
  --qa-out data\processed\ird\extraction_qa_report.md `
  --skip-missing
```

Quick check:

```powershell
.\.venv-backend\Scripts\python.exe scripts\ird_corpus_sqlite.py stats --db data\processed\ird\corpus_v1.sqlite
```

---

## 3. Run the language-model service

### 3.1 Direct (port 8004)

```powershell
cd d:\research\R26-DS-004
$env:PYTHONPATH = "backend\comp-language-model;$PWD"

# Load from .env automatically if COMP_LLM_* vars are set there
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend\comp-language-model `
  --reload `
  --host 127.0.0.1 `
  --port 8004
```

**Verify startup:**

| URL | Expected |
|-----|----------|
| http://127.0.0.1:8004/health | `{"status":"ok",...}` |
| http://127.0.0.1:8004/ready | `corpus_loaded: true` when corpus path is valid |
| http://127.0.0.1:8004/docs | Swagger UI |

Startup logs should mention:

- `Corpus retrieval index loaded` (when corpus exists)
- `TF-IDF intent centroid loaded` (when benchmark JSONL set)
- `GraphService connected` (when Neo4j enabled)

### 3.2 Via API gateway (port 8000)

Terminal 1 — language model (as above).

Terminal 2 — gateway:

```powershell
cd d:\research\R26-DS-004
$env:PYTHONPATH = "$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend\api-gateway `
  --host 127.0.0.1 `
  --port 8000
```

Gateway routes:

| Browser / curl path | Upstream |
|--------------------|----------|
| `POST /api/v1/llm/nlu/parse` | `POST /api/v1/nlu/parse` |
| `POST /api/v1/llm/query` | `POST /api/v1/query` |
| `POST /api/v1/llm/chat` | `POST /api/v1/chat` |

### 3.3 Frontend dashboard

```powershell
cd d:\research\R26-DS-004\frontend
npm install
npm run dev
```

Open:

- http://127.0.0.1:5173/language-model/nlu — intent + retrieval demo
- http://127.0.0.1:5173/language-model/query — citations + optional summary + graph panel

Ensure gateway (8000) and language-model (8004) are both running so the UI can reach `/api/v1/llm/...`.

---

## 4. Manual API tests (curl / PowerShell)

### 4.1 Health

```powershell
Invoke-RestMethod http://127.0.0.1:8004/health
Invoke-RestMethod http://127.0.0.1:8004/ready
```

### 4.2 NLU parse (intent + retrieval)

```powershell
$body = @{ utterance = "What is personal relief for salaried employees?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/nlu/parse `
  -ContentType "application/json" -Body $body
```

Check response fields:

- `normalized_utterance` — after Singlish/informal cleanup
- `predicted_intent` — e.g. `personal_relief`
- `retrieval_hits` — ranked chunk IDs with scores
- `graph_context` — present when Neo4j enabled

### 4.3 Law-grounded query (citations + Proof Map)

```powershell
$body = @{
  question = "What is personal relief in Sri Lanka?"
  top_k = 5
  synthesize_answer = $false
  include_proof_map = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/query `
  -ContentType "application/json" -Body $body
```

Check:

- `citations[].text` — excerpt from corpus
- `citations[].section_uid`, `tier`, `instrument_type` — KG join metadata
- `proof_map.steps` — auditable trail (input → retrieval → evidence → …)
- `domain_status` — should be `in_domain` for tax questions

### 4.4 Query with Gemini summary + Think Twice

Requires `COMP_LLM_ANSWER_SYNTHESIS_ENABLED=true` and `COMP_LLM_GEMINI_API_KEY`.

```powershell
$body = @{
  question = "Explain personal relief for assessment year 2025_26"
  synthesize_answer = $true
  assessment_year_hint = "2025_26"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/query `
  -ContentType "application/json" -Body $body
```

Check:

- `plain_answer` — Gemini summary grounded in citations
- `validation_status` — `passed`, `corrected`, or `skipped`
- If the draft states wrong relief amount, Think Twice sets `validation_status=corrected` and replaces with safe fallback

### 4.5 Multi-turn chat

```powershell
# Turn 1 — new session
$body = @{
  message = "What is personal relief?"
  synthesize_answer = $false
} | ConvertTo-Json

$r1 = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/chat `
  -ContentType "application/json" -Body $body

$session = $r1.session_id
Write-Host "Session:" $session

# Turn 2 — follow-up
$body2 = @{
  session_id = $session
  message = "Does it apply to non-residents?"
  synthesize_answer = $false
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/chat `
  -ContentType "application/json" -Body $body2
```

Check `history_length` increases and `query_result` contains citations.

### 4.6 Off-topic rejection (domain gate)

```powershell
$body = @{ question = "What is the weather in Colombo?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/api/v1/query `
  -ContentType "application/json" -Body $body
```

Expect `domain_status: off_topic` and empty `citations`.

---

## 5. Automated tests

> **Important:** Do not run pytest on the whole `backend/` tree at once — multiple services use a package named `app`. Run tests **per component**.

### 5.1 Language-model unit + API tests

```powershell
cd d:\research\R26-DS-004
$env:PYTHONPATH = "backend\comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend\comp-language-model\app\tests -q --tb=short
```

Expected: **30+ tests pass**; 2 may **skip** if `sentence-transformers` is not installed.

Run Phase 5/6 tests only:

```powershell
.\.venv-backend\Scripts\python.exe -m pytest backend\comp-language-model\app\tests\test_phase5_phase6.py -v
```

### 5.2 Phase 2 regression smoke (corpus fixtures)

```powershell
.\.venv-backend\Scripts\python.exe scripts\phase2_regression_smoke.py
```

### 5.3 Retrieval evaluation (needs real corpus)

```powershell
.\.venv-backend\Scripts\python.exe scripts\phase2_eval_retrieval_tfidf.py `
  --corpus-jsonl data\processed\ird\corpus_v1.jsonl `
  --benchmark evaluation\benchmark_seed_template.jsonl `
  --k 8
```

### 5.4 Symbolic engine (quick Python check)

```powershell
$env:PYTHONPATH = "backend\comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -c "
from app.services.symbolic_engine import validate_advisory_text
bad = validate_advisory_text('Personal relief for 2025_26 is LKR 500,000.', assessment_year_hint='2025_26')
good = validate_advisory_text('Personal relief for 2025_26 is LKR 1,800,000.', assessment_year_hint='2025_26')
print('bad passed:', bad.passed, 'issues:', len(bad.issues))
print('good passed:', good.passed)
"
```

---

## 6. Optional: Neo4j graph enrichment

1. Start Neo4j (Desktop or Docker).
2. Apply schema:

```powershell
pip install -r knowledge_graph\requirements-neo4j.txt
$env:NEO4J_URI = "neo4j://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<password>"
.\.venv-backend\Scripts\python.exe scripts\neo4j_apply_schema.py
```

3. Load corpus chunks:

```powershell
.\.venv-backend\Scripts\python.exe scripts\neo4j_load_corpus_chunks.py `
  --corpus-jsonl data\processed\ird\corpus_v1.jsonl `
  --strict-doc-meta
```

4. Set in `.env`: `COMP_LLM_GRAPH_ENABLED=true` and restart the service.

Re-run a query — `graph_context` should list concepts, reliefs, or lex override notes.

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `stub-no-corpus` in responses | Set `COMP_LLM_CORPUS_JSONL` to a valid JSONL path |
| `corpus_loaded: false` on `/ready` | File path wrong or file missing — rebuild corpus |
| Empty `predicted_intent` | Set `COMP_LLM_INTENT_BENCHMARK_JSONL` |
| `domain_status: off_topic` for valid tax Q | Rephrase with tax keywords; or lower `COMP_LLM_MIN_RETRIEVAL_SCORE` |
| `domain_status: weak_match` | Corpus may not contain relevant passages — check retrieval eval |
| No `plain_answer` | Enable synthesis + set Gemini API key |
| `validation_status: corrected` | Think Twice rejected draft — check `proof_map` symbolic step |
| Graph context always null | Enable `COMP_LLM_GRAPH_ENABLED` and verify Neo4j credentials |
| `ImportPathMismatchError` in pytest | Run pytest only on `backend/comp-language-model/app/tests` |
| Frontend 502 / network error | Start gateway (8000) and language-model (8004) |
| Dense tests skipped | `pip install -r backend/requirements-retrieval-dense.txt` |

---

## 8. API reference (your component)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/ready` | Corpus / index readiness |
| POST | `/api/v1/nlu/parse` | Intent + retrieval hits + graph context |
| POST | `/api/v1/query` | Citations + optional answer + Proof Map |
| POST | `/api/v1/chat` | Multi-turn session with same pipeline |
| DELETE | `/api/v1/chat/sessions/{session_id}` | Remove demo session |

Interactive docs: http://127.0.0.1:8004/docs

---

## 9. Quick daily workflow

```powershell
# 1. Activate venv
cd d:\research\R26-DS-004
.\.venv-backend\Scripts\Activate.ps1

# 2. Run tests before coding
$env:PYTHONPATH = "backend\comp-language-model;$PWD"
pytest backend\comp-language-model\app\tests\test_phase5_phase6.py -q

# 3. Start service
$env:PYTHONPATH = "backend\comp-language-model;$PWD"
python -m uvicorn app.main:app --app-dir backend\comp-language-model --reload --port 8004

# 4. (Optional) Gateway + frontend in other terminals
```

---

## 10. Related docs

| File | Purpose |
|------|---------|
| [`PHASES_RUNBOOK.md`](PHASES_RUNBOOK.md) | Full team runbook (Phases 1–3) |
| [`component-c-language-model-guide.md`](component-c-language-model-guide.md) | Architecture + status overview |
| [`component-c-completion-todo.md`](component-c-completion-todo.md) | What’s left to finish the component |
| [`../reasoning/symbolic_rules_v1.json`](../reasoning/symbolic_rules_v1.json) | Think Twice rule definitions |
