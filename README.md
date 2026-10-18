# AI Tax Advisory System

Monorepo for final-year research on intelligent, explainable tax advisory
(Sri Lanka Inland Revenue Act).

**Canonical extra runbooks (do not duplicate here):**

- [docs/PHASE1_STRUCTURE.md](docs/PHASE1_STRUCTURE.md) — where code belongs (shared vs component)
- [docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md) — Component 4 corpus, eval, dense retrieval, citations

---

## Git workflow for collaborators

Run these from the repository root (`bash` / `zsh`; Git Bash or WSL on Windows).

### Check status

```bash
git status
```

### See differences

```bash
git diff
git diff --staged
```

### Switch branch or create a new one

```bash
git switch main
git switch your-branch-name
git switch -c your-branch-name
```

### Update `main` from GitHub

```bash
git pull origin main
```

### Update your branch with the latest `main`

```bash
git fetch origin main
git merge origin/main
```

### Save changes and push

```bash
git add .
git commit -m "Describe your change"
git push origin your-branch-name
git push -u origin your-branch-name
```

Use `-u` only the first time you push a new branch so later you can run `git push` with no arguments.

---

## Research components and ports

| # | Component | Backend folder | Default port | Vite proxy prefix |
|---|-----------|----------------|--------------|-------------------|
| — | API Gateway | `backend/api-gateway` | **8000** | `/api` (fallback) |
| 1 | Transaction Semantic Reasoning | `backend/comp-transaction-sementic` | **8001** | `/api/v1/documents`, `/transactions`, … |
| 2 | Tax Strategy Optimization | `backend/comp-tax-optimization` | **8002** | `/api/v1/optimization` |
| 3 | Personalized Recommendation | `backend/comp-personalized-recommendation` | **8003** | `/api/v1/recommendation` |
| 4 | Tax Advisory Language Model | `backend/comp-language-model` | **8004** | via gateway `/api/v1/llm` |
| 5 | Adaptive Tax Configuration | `backend/comp-adaptive-tax` | **8005** | `/api/v1/adaptive-tax` |
| — | Frontend (Vite) | `frontend/` | **5173** | — |

**Frontend** talks to backends through the Vite dev proxy. You do **not** need the gateway running for Comp 1–3 and 5 during local UI work. Comp 4 still goes through the gateway (`:8000`) unless you add a dedicated proxy.

Comp 2 and Comp 5 both historically defaulted toward `:8002` in some docs; in this repo Comp 5 is **`:8005`**. Do not bind both to the same port.

---

## Recommended environment

- OS: macOS, Linux, or Windows (WSL2 / Git Bash / PowerShell)
- Python **3.11+**
- Node.js **18.18+** (20 LTS recommended)
- Docker Desktop (optional, local Postgres)
- Git 2.40+

Two **separate** Python venvs — never mix ML packages into the backend venv:

```text
.venv-backend/   # FastAPI services + scripts
.venv-ml/        # models/, notebooks/
```

---

## One-time setup

```bash
git clone <repo-url>
cd R26-DS-004

python3 -m venv .venv-backend
source .venv-backend/bin/activate          # Windows: .\.venv-backend\Scripts\Activate.ps1
pip install -U pip
pip install -r backend/requirements.txt

deactivate
python3 -m venv .venv-ml
source .venv-ml/bin/activate
pip install -r models/requirements-ml.txt

cp .env.example .env
# Fill DATABASE_PASSWORD (ask team lead). Confirm DATABASE_MODE=azure for shared data.

cd frontend
npm install
```

Windows PowerShell venv create:

```powershell
python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
pip install -U pip
pip install -r backend/requirements.txt
```

### Database

Shared **Azure Database for PostgreSQL**. Set in `.env`:

- `DATABASE_MODE=azure` — teammates see the same profiles (needed for auditor/user demo)
- `DATABASE_MODE=local` — Docker Postgres only on your machine
- `DATABASE_MODE=sqlite` — file DB at `SQLITE_PATH` (isolated)

If Azure is stopped:

```bash
az postgres flexible-server start --resource-group tax-advisory-rg --name tax-advisory-db-tax
```

Local Postgres fallback:

```bash
docker compose -f docker/docker-compose.yml up -d postgres
# then DATABASE_MODE=local in .env
```

Init / migrate (from repo root, backend venv active):

```bash
python -m scripts.init_db
alembic upgrade head
```

---

## How to run (copy-paste)

All backend commands assume **repo root** and `.venv-backend` activated.  
**PYTHONPATH** must include the **component directory** (so `app` / `tax_opt_b_app` / `adaptive_tax_app` resolve) **and** the repo root (so `backend.shared` imports work). Never run `pytest backend/` as one tree — several packages are named `app`.

### Minimum for taxpayer dashboard + auditor profiles (Comp 3)

You need **two terminals**: recommendation API + frontend.

**macOS / Linux**

```bash
# Terminal A — Component 3 (:8003)
cd /path/to/R26-DS-004
source .venv-backend/bin/activate
export PYTHONPATH="backend/comp-personalized-recommendation:${PWD}"
uvicorn app.main:app --app-dir backend/comp-personalized-recommendation --reload --host 127.0.0.1 --port 8003
```

```bash
# Terminal B — Frontend (:5173)
cd /path/to/R26-DS-004/frontend
npm run dev
```

**Windows PowerShell**

```powershell
# Terminal A
cd path\to\R26-DS-004
$env:PYTHONPATH = "backend/comp-personalized-recommendation;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-personalized-recommendation --reload --host 127.0.0.1 --port 8003
```

```powershell
# Terminal B
cd path\to\R26-DS-004\frontend
npm run dev
```

Open **http://127.0.0.1:5173/login** (Vite may auto-open the tax explorer; just change the path).

| Role | Username | Password |
|------|----------|----------|
| Auditor | `Auditor` | `auditor@123` |
| Taxpayer | profile `full_name` (e.g. `Taxpayer_00002`) | derived: `Taxpayer_00002` → `2@Tax` |

**Check the new user flow**

1. Log in as **Auditor** → sidebar **Profile** (`/profile`) → create a profile (wizard). Confirm it appears under Recent profiles (Azure = teammates see it too).
2. Sign out.
3. Log in as that taxpayer → you should land on **http://127.0.0.1:5173/taxwise** (TaxWise dark dashboard).
4. Click **Your profile** or sidebar **Profile** → `/taxwise/profile` (bridges to Comp 3 **My Profile** at `/portal/summary?tab=profile` until a TaxWise profile page exists).
5. **← Back to dashboard** returns to `/taxwise`.

**Do not confuse:** auditor Comp 3 **`/profile`** (create/manage profiles) vs TaxWise **`/taxwise/profile`** (taxpayer) vs Comp 3 hub **`/portal/summary`**.

Marketing landing (no login): **http://127.0.0.1:5173/demo**

---

### Component 1 — Transaction semantic (`:8001`)

Backend lives in `backend/comp-transaction-sementic` (folder spelling is intentional / historical).  
The Vite proxy sends `/api/v1/documents`, `/api/v1/transactions`, `/api/v1/taxonomy`, and `/api/v1/taxable-income` to this service (rewritten to `/v1/...`). **Gateway is not required** for this UI.

You need **two terminals**: Comp 1 API + frontend. `.env` should have `DATABASE_MODE` set (`azure` / `local` / `sqlite`) so extraction can persist.

**macOS / Linux — Terminal A (API)**

```bash
cd /path/to/R26-DS-004
source .venv-backend/bin/activate
export PYTHONPATH="${PWD}"
python scripts/run_transaction_semantic_api.py
```

Equivalent uvicorn (same ports / paths the runner sets):

```bash
export PYTHONPATH="backend/comp-transaction-sementic:${PWD}"
uvicorn app.main:app --app-dir backend/comp-transaction-sementic --reload --host 127.0.0.1 --port 8001
```

**Windows PowerShell — Terminal A**

```powershell
cd path\to\R26-DS-004
$env:PYTHONPATH = "$PWD"
.\.venv-backend\Scripts\python.exe scripts\run_transaction_semantic_api.py
```

**Terminal B — Frontend**

```bash
cd /path/to/R26-DS-004/frontend
npm run dev
```

| What | URL |
|------|-----|
| Health | http://127.0.0.1:8001/health |
| OpenAPI | http://127.0.0.1:8001/docs |
| Documents UI | http://127.0.0.1:5173/transaction-documents |
| Tax classification UI | http://127.0.0.1:5173/transaction-tax |

**Smoke-test the API**

```bash
curl -s http://127.0.0.1:8001/health
curl -s "http://127.0.0.1:8001/v1/taxonomy/income-types" | head
```

Analyze one row (no persist):

```bash
curl -s -X POST http://127.0.0.1:8001/v1/transactions/analyze-batch \
  -H "Content-Type: application/json" \
  -d '{"bank_code":"NTB","document_type":"bank_statement","persist":false,"items":[{"row_id":"row-1","raw_desc":"SALARY CREDIT ABC LTD","amount_lkr":"150000.00","tx_date":"2025-01-15","direction":"CR"}]}'
```

**UI test (before changing the classifier)**

1. Open **http://127.0.0.1:5173/transaction-documents**.
2. Upload a Sri Lankan bank PDF/CSV (NTB, BOC, Sampath, Dialog Finance, FriMi, etc.).
3. Confirm extracted rows appear (dates, descriptions, CR/DR, amounts).
4. Open **http://127.0.0.1:5173/transaction-tax** → classify the document.
5. Check **Guaranteed taxable inflows** / **Presumptive assessable**, and the relief **warning** (Comp 2/5 only — Comp 1 does not apply the LKR 1.8M personal relief or compute tax).
6. Use **Grouped similar transactions** (select all / bulk override) or **All classified rows** (one-by-one). Activity grouping lives on Tax classification only — Documents is upload / preview / save.

Activity grouping lexicon: `models/transaction-semantic/data/activity_merchant_lexicon.yaml`.

Layer 1 settles bank codes (`Int.Pd`, `WTax.Pd`, `TOPUP_` from linked banks, POS/FT fees, outbound FTs). Unlabelled `INVCEFT` / `FT FROM_DFP` credits stay in **review** but are **included in the presumptive taxable total** until an auditor override (loan / gift / own transfer / invoice). Demo taxpayer: `taxpayer_00001`.

**Automated tests** (repo root, backend venv; do **not** mix with other `app` packages):

```bash
export PYTHONPATH="backend/comp-transaction-sementic:${PWD}"
python -m pytest backend/comp-transaction-sementic/tests -q --tb=short
```

```powershell
$env:PYTHONPATH = "backend/comp-transaction-sementic;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-transaction-sementic/tests -q --tb=short
```

If port `8001` is busy: `lsof -i :8001` (macOS/Linux) or `netstat -ano | findstr :8001` (Windows), then stop that process.

---

### Component 2 — Tax optimization (`:8002`)

```bash
export PYTHONPATH="backend/comp-tax-optimization:${PWD}"
uvicorn tax_opt_b_app.main:app --app-dir backend/comp-tax-optimization --reload --host 127.0.0.1 --port 8002
```

```powershell
$env:PYTHONPATH = "backend/comp-tax-optimization;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn tax_opt_b_app.main:app `
  --app-dir backend/comp-tax-optimization --reload --host 127.0.0.1 --port 8002
```

UI: http://127.0.0.1:5173/tax-optimization/explorer (Vite may open this by default)

---

### Component 3 — Personalized recommendation (`:8003`)

See **Minimum for taxpayer dashboard** above.

Auditor UI: `/profile`, `/hybrid`, `/impact`, `/compare` (cream AppShell).
Taxpayer TaxWise UI: `/login` → `/taxwise` (new user-view). Comp 3 onboarding/hub: `/portal/financial-intake`, `/portal/about-you`, `/portal/summary`.

OpenAPI: http://127.0.0.1:8003/docs

---

### Component 4 — Language model (`:8004`) + gateway (`:8000`)

```bash
# Terminal 1 — LLM
export PYTHONPATH="backend/comp-language-model:${PWD}"
# Optional Phase 2:
# export COMP_LLM_CORPUS_JSONL=data/processed/corpus_v1.jsonl
# export COMP_LLM_INTENT_BENCHMARK_JSONL=evaluation/benchmark_seed_template.jsonl
# export COMP_LLM_RETRIEVAL_BACKEND=tfidf
uvicorn app.main:app --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

```bash
# Terminal 2 — Gateway
export PYTHONPATH="backend/api-gateway:${PWD}"
uvicorn app.main:app --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000
```

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004

$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000
```

| What | URL |
|------|-----|
| LLM OpenAPI | http://127.0.0.1:8004/docs |
| Gateway health | http://127.0.0.1:8000/health |
| NLU parse | `POST http://127.0.0.1:8000/api/v1/llm/nlu/parse` |
| Query + citations | `POST http://127.0.0.1:8000/api/v1/llm/query` |
| UI | http://127.0.0.1:5173/language-model/nlu |

Copy-paste eval/corpus steps: [docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md).

---

### Component 5 — Adaptive tax (`:8005`)

```bash
export PYTHONPATH="backend/comp-adaptive-tax:${PWD}"
uvicorn adaptive_tax_app.main:app --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

UI: http://127.0.0.1:5173/adaptive-tax/home  

Extra extract deps / amendment demo: [docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md) (Adaptive Tax section).

---

### Frontend only

```bash
cd frontend
npm install    # first time
npm run dev    # http://127.0.0.1:5173
npm run typecheck
npm run lint
```

---

## Full stack (all terminals)

From repo root, typical local demo:

1. Comp 3 `:8003` (profiles + login)  
2. Frontend `:5173`  
3. Comp 1 `:8001` for documents + tax classification  
4. Optional: Comp 2 `:8002`, Comp 4 `:8004`, gateway `:8000`, Comp 5 `:8005`

Port in use:

```bash
lsof -i :8003          # macOS / Linux
netstat -ano | findstr :8003   # Windows
```

---

## Quality gates

```bash
# Backend (venv active) — run ONE component at a time
export PYTHONPATH="backend/comp-transaction-sementic:${PWD}"
python -m pytest backend/comp-transaction-sementic/tests -q --tb=short

export PYTHONPATH="backend/comp-personalized-recommendation:${PWD}"
python -m pytest backend/comp-personalized-recommendation/app/tests -q --tb=short

export PYTHONPATH="backend/comp-language-model:${PWD}"
python -m pytest backend/comp-language-model/app/tests -q --tb=short

export PYTHONPATH="backend/comp-tax-optimization:${PWD}"
python -m pytest backend/comp-tax-optimization/tax_opt_b_app/tests -q --tb=short

export PYTHONPATH="backend/comp-adaptive-tax:${PWD}"
python -m pytest backend/comp-adaptive-tax/adaptive_tax_app/tests -q --tb=short

export PYTHONPATH="backend/api-gateway:${PWD}"
python -m pytest backend/api-gateway/app/tests -q --tb=short

python -m pytest scripts -q --tb=short

# Lint / format
python -m ruff check backend scripts --fix
python -m black backend scripts models

cd frontend && npm run typecheck && npm run lint
```

**Do not** run `pytest backend/` in one command (`ImportPathMismatchError` from multiple `app` packages).

---

## Repo layout (actual)

```text
R26-DS-004/
├── backend/
│   ├── api-gateway/
│   ├── shared/                          # DB, settings, schemas
│   ├── comp-transaction-sementic/
│   ├── comp-tax-optimization/
│   ├── comp-personalized-recommendation/
│   ├── comp-language-model/
│   └── comp-adaptive-tax/
├── frontend/src/
│   ├── features/                        # auditor + component UIs
│   └── pages/
│       ├── demo/                        # marketing landing /demo
│       └── user-view/                   # TaxWise taxpayer shell (/taxwise)
├── models/
├── scripts/
├── docs/
└── README.md
```
