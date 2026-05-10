# AI Tax Advisory System

Standardized monorepo scaffold for final-year research on intelligent, explainable tax advisory.

## Git workflow for collaborators

Run these from the repository root (`bash` / `zsh`; Git Bash or WSL on Windows).

### Check status

git status

### See differences

git diff

git diff --staged

### Switch branch or create a new one

git switch main

git switch your-branch-name

git switch -c your-branch-name

### Update `main` from GitHub

git pull origin main

### Update your branch with the latest `main`

git fetch origin main

git merge origin/main

### Save changes and push

git add .

git commit -m "Describe your change"

git push origin your-branch-name

git push -u origin your-branch-name

Use `-u` only the first time you push a new branch so later you can run `git push` with no arguments.

## Research Components

1. Financial Transaction Semantic Reasoning and Taxable Income Inference
2. Tax Strategy Optimization and Explainable Decision Engine
3. Personalized Recommendation and Predictive Impact Modeling Engine
4. Intelligent Tax Advisory Language Model

## Standard Project Structure

```text
ai-tax-advisory-system/
├── backend/
│   ├── api-gateway/
│   ├── shared/
│   │   ├── schemas/
│   │   ├── utils/
│   │   └── config/
│   ├── comp-transaction-sementic/
│   ├── comp-tax-optimization/
│   ├── comp-personalized-recommendation/
│   └── comp-language-model/
├── frontend/
├── data/
│   ├── synthetic/
│   └── processed/
├── models/
│   ├── transaction-semantic/
│   ├── tax-optimization/
│   ├── personalized-recommendation/
│   └── language-model/
├── notebooks/
├── docker/
└── README.md
```

## Phase 1 Team Boundary Guide

Before adding new code in shared folders or component folders, follow:

- `docs/PHASE1_STRUCTURE.md`

This keeps model-specific and common code separated while avoiding breaking changes for teammates.

## Language model research — phase runbook (tests & corpus)

**Component 4 (Intelligent Tax Advisory Language Model):** step-by-step commands for **Phase 1**, **Phase 1b**, and placeholders for later phases live in one file so you can copy-paste without hunting through chat history.

- **[docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md)** — run tests, IRD corpus pipeline, SQLite/QA; Phase 2 **M5** [`evaluation/frozen/`](evaluation/frozen/); **Steps 6–8** leaderboard / CI smoke / handoff report; **Step 9** [`scripts/phase2_split_benchmark.py`](scripts/phase2_split_benchmark.py); **Step 10** held-out eval; **Step 11** dense retrieval ([`backend/requirements-retrieval-dense.txt`](backend/requirements-retrieval-dense.txt)); **Step 12** NLU API dense; **Step 13** retrieval MRR + [`scripts/phase2_merge_benchmark_splits.py`](scripts/phase2_merge_benchmark_splits.py); **Step 14** [`POST /api/v1/query`](docs/PHASES_RUNBOOK.md) (citations).

## Recommended Common Environment (for all users)

- OS: macOS, Linux, or Windows (WSL2 preferred for Windows)
- Python: 3.11+
- Node.js: 20 LTS+
- Package managers: `pip` and `npm`
- Container runtime: Docker Desktop (or Docker Engine + Compose)
- Git: 2.40+

## Quick Setup

### 1. Clone and create virtual environments

```bash
git clone <repo-url>
cd -Intelligent-Tax-Advisory-Language-Model

# Backend environment
python3 -m venv .venv-backend
source .venv-backend/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# ML environment (separate venv)
deactivate
python3 -m venv .venv-ml
source .venv-ml/bin/activate
pip install --upgrade pip
pip install -r models/requirements-ml.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and replace `<ask-team-lead-for-password>` with the actual database password (ask the team lead).

### 3. Initialize the database

Make sure the Azure PostgreSQL server is running (it may be stopped to save credits), then:

```bash
source .venv-backend/bin/activate
python -m scripts.init_db
```

This will create the `tax_advisory` database if it doesn't exist and verify the connection.

### 4. Run database migrations

```bash
alembic upgrade head
```

## Database

The project uses a shared **Azure Database for PostgreSQL - Flexible Server** (Central India region).

- **Host:** `tax-advisory-db.postgres.database.azure.com`
- **Database:** `tax_advisory`
- **SSL:** Required

The server is stopped when not in use to conserve Azure for Students credits. If you get a connection error, ask the team lead to start the server, or start it yourself:

```bash
az postgres flexible-server start \
  --resource-group tax-advisory-rg \
  --name tax-advisory-db
```

To stop when done for the day:

```bash
az postgres flexible-server stop \
  --resource-group tax-advisory-rg \
  --name tax-advisory-db
```

### Local Postgres fallback (when Azure is stopped)

A `docker/docker-compose.yml` ships a local Postgres (and optional MLflow)
so development isn't blocked when the Azure server is off.

```bash
docker compose -f docker/docker-compose.yml up -d postgres
# then in .env
# DATABASE_MODE=local
```

## Running the services

### Component 4 — Language model backend + API gateway + frontend (this module)

The **dashboard** (`frontend/`) sends browser calls to **`/api` → API gateway (`:8000`)**. Routes under **`/api/v1/llm/**`** are proxied to the **language-model service** (default **`http://127.0.0.1:8004`**, see `COMP_LLM_URL` in `backend/shared/config/settings.py` or `.env`). You need **three terminals** from the repo root (or use your IDE run configs).

**Windows (PowerShell)**

```powershell
# Terminal 1 — Language model (Component 4), port 8004
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
# Optional — Phase 2 retrieval + intent + citations (paths relative to repo root):
# $env:COMP_LLM_CORPUS_JSONL = "data/processed/corpus_v1.jsonl"
# $env:COMP_LLM_INTENT_BENCHMARK_JSONL = "evaluation/benchmark_seed_template.jsonl"
# $env:COMP_LLM_RETRIEVAL_BACKEND = "tfidf"   # or "dense" after: pip install -r backend/requirements-retrieval-dense.txt
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

```powershell
# Terminal 2 — API gateway, port 8000 (if the port is busy, stop the other process first)
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 3 — Frontend (Vite)
cd frontend
npm install   # first time only
npm run dev   # http://127.0.0.1:5173 (see terminal if another port is used)
```

**Linux / macOS / Git Bash**

```bash
cd /path/to/R26-DS-004
source .venv-backend/bin/activate
export PYTHONPATH="backend/comp-language-model:${PYTHONPATH:-.}"
# Optional: export COMP_LLM_CORPUS_JSONL=... COMP_LLM_INTENT_BENCHMARK_JSONL=...
uvicorn app.main:app --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

```bash
# Second terminal
source .venv-backend/bin/activate
export PYTHONPATH="backend/api-gateway:${PYTHONPATH:-.}"
uvicorn app.main:app --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000
```

```bash
# Third terminal
cd frontend && npm install && npm run dev
```

**Quick URLs**

| What | URL |
|------|-----|
| Language model OpenAPI | http://127.0.0.1:8004/docs |
| Gateway health | http://127.0.0.1:8000/health |
| NLU parse (via gateway) | `POST http://127.0.0.1:8000/api/v1/llm/nlu/parse` |
| Query + citations (via gateway) | `POST http://127.0.0.1:8000/api/v1/llm/query` |
| **Dashboard — Language Model** (after `npm run dev`) | http://127.0.0.1:5173/language-model/nlu and …/query |

The sidebar section **Language Model** links to **NLU parse** and **Law query** pages (`frontend/src/features/language-model/`). They call the gateway at `/api/v1/llm/nlu/parse` and `/api/v1/llm/query`.

Frontend dev server proxies **`/api`** to the gateway (`VITE_API_BASE_URL`, default `http://127.0.0.1:8000`). More detail: [docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md) (Dashboard + Phase 2 env vars).

---

### Other backends (optimization, recommendation) + gateway

```bash
source .venv-backend/bin/activate

# Component 2 (Tax Strategy Optimization — Function 1 compliance)
PYTHONPATH=. uvicorn tax_opt_b_app.main:app \
  --app-dir backend/comp-tax-optimization \
  --reload --port 8002

# Component 3 (Personalized Recommendation)
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/comp-personalized-recommendation \
  --reload --port 8003

# API Gateway (proxies /api/v1/recommendation/**, /api/v1/optimization/**, /api/v1/llm/**, …)
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/api-gateway \
  --reload --port 8000
```

Use this block when you need the **tax optimization explorer** (direct Vite proxy to `:8002`) and related services; see the runbook **Dashboard** section for the full four-backend layout.

## Quality gates

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files                 # ruff + black + mypy + standard hooks

PYTHONPATH=. pytest                         # run all backend tests
cd frontend && npm run typecheck && npm run lint
```
