# Component C — How to Run & Test

**Component:** Intelligent Tax Advisory Language Model  
**Service:** `backend/comp-language-model` (port **8004**)  
**Student:** IT22896186 (Hewagama S.R)  
**Last updated:** 2026-08-16

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Use `.venv-backend` virtualenv in repo root |
| Node.js | 18+ | For frontend only |
| Neo4j (optional) | 5.x | Only needed for graph enrichment |
| Gemini API key (optional) | — | Only needed for plain-language answers |

---

## 2. One-time setup

```powershell
# From the repo root (D:\research\R26-DS-004)

# Activate the backend venv
.venv-backend\Scripts\Activate.ps1

# Verify packages
pip list | Select-String "fastapi|scikit|pytest"

# Copy and configure .env (only needed once)
# Edit .env and set:
#   COMP_LLM_CORPUS_JSONL=data/processed/ird/corpus_v1.jsonl
#   COMP_LLM_GEMINI_API_KEY=<your-key>   (optional)
#   NEO4J_PASSWORD=taxkg2025              (only if using Neo4j)
```

### Build the corpus (if missing)

```powershell
py -3 scripts/ird_phase1b_finalize.py
# Produces: data/processed/ird/corpus_v1.jsonl
```

---

## 3. Run the service

```powershell
# From repo root, with venv active
$env:PYTHONPATH = "$PWD;$PWD\backend\comp-language-model"
uvicorn app.main:app --app-dir backend/comp-language-model --port 8004 --reload
```

The service starts at **http://localhost:8004**.

| URL | Purpose |
|-----|---------|
| http://localhost:8004/docs | Swagger UI — interactive API explorer |
| http://localhost:8004/health | Health check |
| http://localhost:8004/ready | Readiness check (corpus loaded?) |

---

## 4. Environment flags

| Variable | Default | Effect |
|----------|---------|--------|
| `COMP_LLM_CORPUS_JSONL` | — | Path to corpus JSONL; retrieval disabled if unset |
| `COMP_LLM_RETRIEVAL_BACKEND` | `tfidf` | `tfidf` or `dense` |
| `COMP_LLM_RETRIEVAL_TOP_K` | `8` | Number of chunks returned |
| `COMP_LLM_INTENT_BENCHMARK_JSONL` | — | Intent classifier training data |
| `COMP_LLM_ANSWER_SYNTHESIS_ENABLED` | `false` | Enable Gemini plain-language answers |
| `COMP_LLM_GEMINI_API_KEY` | — | Required for synthesis |
| `COMP_LLM_GRAPH_ENABLED` | `false` | Neo4j knowledge-graph enrichment |
| `COMP_LLM_LEX_SPECIALIS_RERANK` | `true` | Tier/instrument boost after retrieval |
| `COMP_LLM_THINK_TWICE_ENABLED` | `true` | Symbolic validation on synthesized answers |
| `COMP_LLM_PROOF_MAP_ENABLED` | `true` | Attach Proof Map to /query and /chat responses |

---

## 5. Run automated tests

```powershell
# From repo root
$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\ -v --tb=short
```

**Expected result:** 32 passed, 2 skipped (skips = `sentence_transformers` not installed; optional).

### Run specific test groups

```powershell
# Health endpoints only
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_health.py -v

# NLU + retrieval
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_nlu.py -v

# Query + chat API
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_query.py -v

# Phase 5/6 neuro-symbolic core (symbolic engine, Think Twice, Proof Map, Lex Specialis)
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_phase5_phase6.py -v

# M5 frozen contract (schema stability)
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_m5_frozen_contract.py -v

# Domain gate (off-topic rejection)
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_domain_gate.py -v

# Dense retrieval + embedding bundle
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\test_dense_embedding_bundle.py -v
```

---

## 6. Manual API tests (with service running on port 8004)

### Health check

```powershell
Invoke-RestMethod http://localhost:8004/health
Invoke-RestMethod http://localhost:8004/ready
```

### NLU parse

```powershell
$body = @{ utterance = "What is the personal relief for 2025_26?"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/nlu/parse `
  -ContentType "application/json" -Body $body
```

Expected fields: `predicted_intent`, `retrieval_hits[]`, `domain_status`, `model`.

### Law-grounded query (with Proof Map)

```powershell
$body = @{
  question = "What is personal relief for a resident individual in 2025_26?"
  top_k = 5
  synthesize_answer = $false
  include_proof_map = $true
  assessment_year_hint = "2025_26"
} | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/query `
  -ContentType "application/json" -Body $body
```

Expected fields: `citations[]` each with `text`, `tier`, `source_doc_id`; `proof_map.steps[]`.

### Query with Gemini synthesis + Think Twice

```powershell
# Requires COMP_LLM_ANSWER_SYNTHESIS_ENABLED=true and COMP_LLM_GEMINI_API_KEY set
$body = @{
  question = "Explain the personal relief for 2025_26"
  synthesize_answer = $true
  include_proof_map = $true
  assessment_year_hint = "2025_26"
} | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/query `
  -ContentType "application/json" -Body $body
```

Expected fields: `plain_answer`, `validation_status` (passed/corrected), `proof_map`.

### Multi-turn chat

```powershell
# Turn 1 — new session
$body = @{ message = "What is personal relief?" } | ConvertTo-Json
$r1 = Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/chat `
  -ContentType "application/json" -Body $body
$sid = $r1.session_id
Write-Host "Session: $sid"

# Turn 2 — follow-up in same session
$body2 = @{ message = "What about for 2024_25?"; session_id = $sid } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/chat `
  -ContentType "application/json" -Body $body2

# Delete session
Invoke-RestMethod -Method DELETE -Uri "http://localhost:8004/api/v1/chat/sessions/$sid"
```

### Domain gate — off-topic rejection

```powershell
$body = @{ utterance = "What is the weather today?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method POST -Uri http://localhost:8004/api/v1/nlu/parse `
  -ContentType "application/json" -Body $body
# Expect: domain_status = "off_topic"
Write-Host $r.domain_status
```

### Symbolic validation check (direct unit test)

```powershell
$env:PYTHONPATH = "D:\research\R26-DS-004;D:\research\R26-DS-004\backend\comp-language-model"
.venv-backend\Scripts\python -c @"
from app.services.symbolic_engine import validate_advisory_text
# Wrong personal relief — should FAIL
r = validate_advisory_text('Personal relief for 2025_26 is LKR 500,000.', assessment_year_hint='2025_26')
print('passed:', r.passed, '| issues:', [i.code for i in r.issues])

# Correct personal relief — should PASS
r2 = validate_advisory_text('Personal relief for 2025_26 is LKR 1,800,000.', assessment_year_hint='2025_26')
print('passed:', r2.passed, '| issues:', [i.code for i in r2.issues])

# Invalid WHT rate — warning
r3 = validate_advisory_text('Withholding tax of 25% applies.')
print('passed:', r3.passed, '| issues:', [i.code for i in r3.issues])
"@
```

---

## 7. Test what each feature validates

| Feature | Test file | Key assertions |
|---------|-----------|----------------|
| TF-IDF retrieval | `test_nlu.py` | Returns top chunk from in-memory corpus |
| Dense retrieval (optional) | `test_dense_embedding_bundle.py` | Loads bundle, cosine search works |
| Intent classification | `test_nlu.py` | Predicts intent from benchmark labels |
| Domain gate | `test_domain_gate.py` | Rejects weather/sports, passes tax |
| Lex Specialis rerank | `test_phase5_phase6.py` | Tier A beats Tier C after rerank |
| Singlish normalisation | `test_phase5_phase6.py` | "free lance" → "freelance" |
| Personal relief rule | `test_phase5_phase6.py` | 500k rejected; 1.8M accepted for 2025_26 |
| WHT rate rule | `test_phase5_phase6.py` | 14% valid; 25% flagged as unrecognised |
| Rate cap rule | `test_phase5_phase6.py` | 45% rejected; max is 36% |
| Think Twice correction | `test_phase5_phase6.py` | Bad answer replaced with safe fallback |
| Proof Map steps | `test_phase5_phase6.py` | user_query, retrieval, evidence steps present |
| Proof Map evidence refs | `test_phase5_phase6.py` | evidence_refs populated from citations |
| Query citations with text | `test_query.py` | Citations include text excerpt and KG fields |
| Multi-turn chat | `test_query.py` | Session created, response contains session_id |
| Schema stability (M5) | `test_m5_frozen_contract.py` | Pydantic schemas match frozen JSON examples |

---

## 8. Frontend — run and test UI

```powershell
# From repo root
cd frontend
npm install      # first time only
npm run dev      # Vite dev server on http://localhost:5173
```

Navigate to:

| URL | What to test |
|-----|-------------|
| `/language-model/chat` | **Multi-turn chat UI** — ask tax questions, enable "Show Proof Maps" checkbox |
| `/language-model/nlu` | NLU parse — see retrieved chunks and intent |
| `/language-model/query` | Law query form — enable "Plain-language summary" if Gemini key set |

### Chat UI golden-path test

1. Go to `/language-model/chat`
2. Type: `What is personal relief for 2025_26?` → Submit
3. Verify: assistant message appears with citations
4. Check "Show Proof Maps" → verify audit trail shows user_query, retrieval, evidence steps
5. Type a follow-up: `What about for non-residents?` — session_id should persist
6. Click "New session" → conversation resets

---

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No module named 'app'` in pytest | Set `PYTHONPATH` as shown in section 5 |
| `corpus_loaded: false` in API response | Set `COMP_LLM_CORPUS_JSONL` in `.env` and build corpus |
| `plain_answer` is null | Set `COMP_LLM_ANSWER_SYNTHESIS_ENABLED=true` and `COMP_LLM_GEMINI_API_KEY` |
| Neo4j connection refused | Set `COMP_LLM_GRAPH_ENABLED=false` or start Neo4j |
| `sentence_transformers` missing | Install: `pip install sentence-transformers` (dense backend only) |
| 2 tests skipped | Expected — `sentence_transformers` optional; TF-IDF tests still run |

---

## 10. Quick daily workflow

```powershell
# 1. Activate venv
.venv-backend\Scripts\Activate.ps1

# 2. Run all component tests
$env:PYTHONPATH = "$PWD;$PWD\backend\comp-language-model"
.venv-backend\Scripts\pytest backend\comp-language-model\app\tests\ -v

# 3. Start service
uvicorn app.main:app --app-dir backend/comp-language-model --port 8004 --reload

# 4. Test health
Invoke-RestMethod http://localhost:8004/health
```
