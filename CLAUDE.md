# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**AI Tax Advisory System** — a monorepo for final-year research on intelligent, explainable tax advisory.

Five research components:
1. **Component 1** — Transaction Semantic Reasoning (`:8001`)
2. **Component 2** — Tax Strategy Optimization (`:8002`)
3. **Component 3** — Personalized Recommendation (`:8003`)
4. **Component 4** — Intelligent Tax Advisory Language Model (`:8004`)
5. **Component 5** — Adaptive Tax Configuration (`:8005`, or shares `:8002` in Phase 2)

Plus an **API Gateway** (`:8000`) that proxies `/api/v1/{component}/**` routes to the appropriate backend, and a **Frontend** (Vite, `:5173`) that consumes the gateway.

---

## Architecture

**Backend:** Python FastAPI services, one per component + shared gateway. Each component is an independent FastAPI app with its own `app/main.py`.

**Shared layer:** `backend/shared/` contains cross-cutting concerns:
- `config/settings.py` — typed settings (DB, gateway URLs, env vars)
- `schemas/` — shared Pydantic models (traceability, etc.)
- `db/` — SQLAlchemy ORM and connection management
- `utils/` — logging, context middleware
- `middleware/` — request context, CORS

**Frontend:** React 19 + TypeScript, Vite, TailwindCSS, React Router, React Query, Zod for validation.

**Database:** Azure Database for PostgreSQL (shared across components). Local Postgres via Docker Compose for development when Azure is stopped. SQLite fallback for isolated testing. Set `DATABASE_MODE` in `.env` to switch (`azure` | `local` | `sqlite`).

---

## Virtual Environments

**Two separate venvs** (important: never mix them):

```
.venv-backend/    # backend services + scripts (Python 3.11+)
.venv-ml/         # ML-specific (models/, notebooks/) with ML packages
```

Create and activate (one-time):
```powershell
python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
pip install -r backend/requirements.txt

deactivate
python -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
pip install -r models/requirements-ml.txt
```

**Linux/macOS:** `source .venv-backend/bin/activate` / `source .venv-ml/bin/activate`.

---

## Common Commands

### Run all tests

> **Critical:** Never run `pytest backend/ scripts/` together in one command. Multiple packages named `app` live under `backend/`, triggering `ImportPathMismatchError`. Run each component separately:

```powershell
# Scripts (chunking, SQLite, outline helpers)
.\.venv-backend\Scripts\python.exe -m pytest scripts -q --tb=short

# Language-model component
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -q --tb=short

# Tax Optimization component
$env:PYTHONPATH = "backend/comp-tax-optimization;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-tax-optimization/tax_opt_b_app/tests -q --tb=short

# Personalized Recommendation component
$env:PYTHONPATH = "backend/comp-personalized-recommendation;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-personalized-recommendation/app/tests -q --tb=short

# Adaptive Tax component
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/adaptive_tax_app/tests -q --tb=short

# Optimization and Explainable
$env:PYTHONPATH = "backend/comp-optimization-explainable;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-optimization-explainable/tests -q --tb=short

# API gateway
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/api-gateway/app/tests -q --tb=short
```

**Single test file:**
```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests/test_module.py -v
```

### Quality gates (ruff, black, mypy, pre-commit)

```powershell
# Auto-format + lint in one pass
.\.venv-backend\Scripts\python.exe -m ruff check backend scripts --fix
.\.venv-backend\Scripts\python.exe -m black backend scripts models

# Type-check (strict mode off, but configured in pyproject.toml)
.\.venv-backend\Scripts\python.exe -m mypy

# All hooks (ruff, black, mypy, + standard git hooks)
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

**Frontend:**
```powershell
cd frontend
npm run typecheck   # tsc --noEmit
npm run lint        # eslint .
```

### Start the full stack (3 terminals from repo root)

**Terminal 1 — Language Model (Component 4, `:8004`):**
```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-language-model --reload --host 127.0.0.1 --port 8004
```

Optional env vars for Phase 2:
```powershell
$env:COMP_LLM_CORPUS_JSONL = "data/processed/corpus_v1.jsonl"
$env:COMP_LLM_INTENT_BENCHMARK_JSONL = "evaluation/benchmark_seed_template.jsonl"
$env:COMP_LLM_RETRIEVAL_BACKEND = "tfidf"   # or "dense" if pip install -r backend/requirements-retrieval-dense.txt
```

**Terminal 2 — API Gateway (`:8000`):**
```powershell
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/api-gateway --reload --host 127.0.0.1 --port 8000
```

**Terminal 3 — Frontend (Vite, `:5173`):**
```powershell
cd frontend
npm install   # first time only
npm run dev
```

**Quick URLs after startup:**
- Frontend: http://127.0.0.1:5173/
- Language model OpenAPI: http://127.0.0.1:8004/docs
- Gateway health: http://127.0.0.1:8000/health
- NLU parse: `POST http://127.0.0.1:8000/api/v1/llm/nlu/parse`
- Query + citations: `POST http://127.0.0.1:8000/api/v1/llm/query`

### Start other components (if needed)

All from repo root. **Note:** Tax Optimization and Adaptive Tax both use port `:8002` by default; run them in separate environments or on different ports.

**Component 1 — Transaction Semantic (`:8001`):**
```powershell
$env:PYTHONPATH = "$PWD"
python scripts/run_transaction_semantic_api.py
```

**Component 2 — Tax Optimization (`:8002`):**
```powershell
$env:PYTHONPATH = "backend/comp-tax-optimization;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn tax_opt_b_app.main:app `
  --app-dir backend/comp-tax-optimization --reload --host 127.0.0.1 --port 8002
```

**Component 3 — Personalized Recommendation (`:8003`):**
```powershell
$env:PYTHONPATH = "backend/comp-personalized-recommendation;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-personalized-recommendation --reload --host 127.0.0.1 --port 8003
```

**Component 5 — Adaptive Tax (`:8005`, or `:8002` if Tax Optimization not running):**
```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --reload --host 127.0.0.1 --port 8005
```

**Optimization and Explainable (`:8008`):**
```powershell
$env:PYTHONPATH = "backend/comp-optimization-explainable;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn opt_explain_app.main:app `
  --app-dir backend/comp-optimization-explainable --reload --host 127.0.0.1 --port 8008
```
UI: http://127.0.0.1:5173/optimization-explainable (year) · `/acts` · `/income` · `/reliefs` · `/result`

**Port allocation notes:**
- Components 2 and 5 both default to `:8002`, so they cannot run simultaneously on the same machine.
- If running both, start one on `:8002` and the other on `:8005` (or another free port).
- Frontend proxies (in `vite.config.ts`) are pre-configured to reach both services.
- API Gateway (`:8000`) dynamically routes to whichever service is running based on the request path.

### Database setup

**Using Azure Postgres:**
```powershell
.\.venv-backend\Scripts\Activate.ps1
python -m scripts.init_db      # Creates tax_advisory database if needed
alembic upgrade head           # Runs all pending migrations
```

**Using local Postgres (when Azure is stopped):**
```bash
docker compose -f docker/docker-compose.yml up -d postgres
# Then in .env:
# DATABASE_MODE=local
```

**Using SQLite (isolated testing):**
```bash
# In .env:
# DATABASE_MODE=sqlite
# SQLITE_PATH=data/dev.db
```

---

## Key Project Files & Directories

| Path | Purpose |
|------|---------|
| `backend/api-gateway/app/main.py` | Router; registers proxy routes for all 5 components |
| `backend/shared/` | DB, settings, schemas, logging, middleware (shared by all components) |
| `backend/comp-language-model/app/main.py` | Component 4 (LLM); NLU parse, query with citations |
| `backend/comp-tax-optimization/tax_opt_b_app/main.py` | Component 2 tax strategy optimization |
| `backend/comp-personalized-recommendation/app/main.py` | Component 3 recommendations |
| `backend/comp-adaptive-tax/adaptive_tax_app/main.py` | Component 5 adaptive tax configuration |
| `backend/comp-optimization-explainable/opt_explain_app/main.py` | Optimization and Explainable (RAG reliefs; port 8008) |
| `backend/comp-transaction-semantic/` | Component 1 transaction parsing |
| `backend/migrations/` | Alembic schema migrations (PostgreSQL) |
| `frontend/src/` | React app; `features/language-model/` for Component 4 UI |
| `models/language-model/` | LLM model artifacts and eval code |
| `evaluation/` | Benchmark datasets, frozen snapshots, leaderboard (Phase 2+) |
| `scripts/` | Utilities: corpus pipeline, chunking, init_db, etc. |
| `docs/PHASES_RUNBOOK.md` | **Single source of truth** for Phase 1, 1b, 2+ commands; copy-paste commands live here |
| `docs/PHASE1_STRUCTURE.md` | Team boundary guide (which code goes where) |

---

## Database & Migrations

**Alembic** manages PostgreSQL schema. Migrations live in `backend/migrations/versions/`.

```powershell
# Create a new migration (after editing SQLAlchemy models)
alembic revision --autogenerate -m "describe change"

# Run pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

Migrations run against the configured database (set `DATABASE_MODE` in `.env`).

---

## PYTHONPATH Gotchas

Multiple packages named `app` live under `backend/`, and some components use custom module names. When running a service or tests, set `PYTHONPATH` to include both:
1. The component directory (so the app module resolves)
2. The repo root (so `backend.shared` imports work)

**App module names by component:**
- Component 1 (Transaction Semantic): `scripts/run_transaction_semantic_api.py` (custom runner)
- Component 2 (Tax Optimization): `tax_opt_b_app.main:app`
- Component 3 (Personalized Recommendation): `app.main:app`
- Component 4 (Language Model): `app.main:app`
- Component 5 (Adaptive Tax): `adaptive_tax_app.main:app`
- Optimization and Explainable: `opt_explain_app.main:app`
- API Gateway: `app.main:app`

Examples:
```powershell
# Language-model component (uses app/main.py)
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/comp-language-model

# Tax Optimization component (uses tax_opt_b_app/main.py)
$env:PYTHONPATH = "backend/comp-tax-optimization;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn tax_opt_b_app.main:app --app-dir backend/comp-tax-optimization

# Adaptive Tax component (uses adaptive_tax_app/main.py)
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app --app-dir backend/comp-adaptive-tax
# Optimization and Explainable (uses opt_explain_app/main.py)
$env:PYTHONPATH = "backend/comp-optimization-explainable;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn opt_explain_app.main:app --app-dir backend/comp-optimization-explainable

# Scripts and general backend code
$env:PYTHONPATH = "$PWD"
python -m scripts.some_script
```

---

## Environment Variables

Key vars in `.env` (copy from `.env.example` and fill in):

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_MODE` | `azure` | Which DB to use: `azure` \| `local` \| `sqlite` |
| `DATABASE_PASSWORD` | `` | Azure Postgres password (ask team lead) |
| `APP_ENV` | `development` | `development` \| `staging` \| `production` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `CORS_ORIGINS` | `["http://127.0.0.1:5173"]` | Frontend origin (for CORS) |
| `COMP_LLM_URL` | `http://localhost:8004` | Component 4 discovery (for gateway) |
| `COMP_LLM_CORPUS_JSONL` | (optional) | Path to Phase 2 corpus (relative to repo root) |
| `COMP_LLM_RETRIEVAL_BACKEND` | `tfidf` | Retrieval mode: `tfidf` \| `dense` |
| `COMP_ADAPTIVE_TAX_URL` | `http://localhost:8005` | Component 5 discovery (for gateway, if running on `:8005`) |
| `COMP_OPTIMIZATION_EXPLAINABLE_URL` | `http://localhost:8008` | Optimization and Explainable discovery (for gateway) |

---

## Code Style & Quality

- **Line length:** 100 (ruff, black)
- **Target Python:** 3.11+
- **Linters:** ruff (E/W/F/I/B/UP/C4/SIM/RUF), black (formatter), mypy (type hints)
- **Exclusions:** `.venv-*`, `frontend/`, `notebooks/`, `backend/migrations/versions/` (auto-generated)
- **Pre-commit hooks:** installed via `pre-commit install` (ruff, black, mypy, standard hooks)

**Notes:**
- `B008` ignored (FastAPI `Depends()` in defaults is allowed)
- Mypy strict mode off; plugins: `pydantic.mypy`
- Test directories skip S101 (assert usage in tests is fine)

---

## Testing Strategy

- **Unit tests:** Live in `app/tests/` within each component
- **Integration tests:** Marked with `pytest.mark.integration`; hit real DB/services
- **Slow tests:** Marked with `pytest.mark.slow`
- **Never mix test trees:** Run `pytest` on each component separately to avoid import name collisions

```powershell
# Run only fast unit tests
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -v -m "not slow and not integration"

# Run integration tests (require DB)
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -v -m integration
```

---

## Frontend Development

- **Build tool:** Vite
- **Framework:** React 19 + TypeScript
- **Routing:** React Router 7
- **Styling:** TailwindCSS 4
- **HTTP client:** axios + React Query
- **Form validation:** React Hook Form + Zod
- **Components:** custom UI component library in `src/components/` (Radix UI primitives)

**Key commands:**
```powershell
cd frontend

npm install                 # Install deps (once)
npm run dev                 # Start dev server (auto-reload)
npm run build               # Prod build to dist/
npm run typecheck           # tsc without emitting
npm run lint                # eslint check
npm run preview             # Preview prod build locally
```

Frontend dev server proxies:
- `/api` → API Gateway (default `http://127.0.0.1:8000`, configurable via `VITE_API_BASE_URL`)
- `/api/v1/optimization` → Component 2 directly (default `http://127.0.0.1:8002`, configurable via `VITE_DEV_OPTIMIZATION_URL`)
- `/api/v1/adaptive-tax` → Component 5 directly (default `http://127.0.0.1:8002`, configurable via `VITE_DEV_ADAPTIVE_TAX_URL`)
- `/api/v1/optimization-explainable` → Optimization and Explainable directly (default `http://127.0.0.1:8008`, configurable via `VITE_DEV_OPTIMIZATION_EXPLAINABLE_URL`)
- `/api/v1/recommendation` → Component 3 directly (default `http://127.0.0.1:8003`, configurable via `VITE_DEV_RECOMMENDATION_URL`)
- `/api/v1/transactions`, `/api/v1/documents`, etc. → Component 1 directly (default `http://127.0.0.1:8001`, configurable via `VITE_DEV_TRANSACTION_SEMANTIC_URL`)

Direct proxies allow development without restarting the gateway and are pre-configured in [frontend/vite.config.ts](frontend/vite.config.ts).

---

## Important References

- **[docs/PHASES_RUNBOOK.md](docs/PHASES_RUNBOOK.md)** — **Canonical source** for Phase 1, 1b, 2+ commands. Copy-paste all runbook commands from here to avoid stale chat history.
- **[docs/PHASE1_STRUCTURE.md](docs/PHASE1_STRUCTURE.md)** — Team boundary guide; which code goes where (model-specific vs. shared).
- **[docs/language-model_phase1_architecture.md](docs/language-model_phase1_architecture.md)** — Component 4 architecture deep-dive.
- **.env.example** — Template for all environment variables; rename to `.env` and fill in secrets.
- **pyproject.toml** — Project metadata, ruff/black/mypy/pytest config.
- **backend/shared/config/settings.py** — Typed settings (one source of truth for DB, gateway, component URLs).

---

## Common Patterns & Conventions

### Adding a new backend service
1. Create `backend/comp-{name}/{app_module}/main.py` (FastAPI entry point; use `app` or a custom module name)
2. Add `COMP_{NAME}_URL` to `backend/shared/config/settings.py`
3. Register proxy route in `backend/api-gateway/app/main.py`
4. Update `vite.config.ts` proxy if frontend needs direct access (optional, bypasses gateway)
5. Update `docs/PHASES_RUNBOOK.md` with startup command
6. Add startup example to CLAUDE.md "Start other components" section with correct PYTHONPATH and app module name

### Adding a new database migration
1. Edit SQLAlchemy models in the relevant component or `backend/shared/db/`
2. Run `alembic revision --autogenerate -m "describe change"`
3. Review generated migration in `backend/migrations/versions/`
4. Run `alembic upgrade head` to apply

### Adding a new environment variable
1. Add field to `Settings` class in `backend/shared/config/settings.py` with a default
2. Document in `.env.example`
3. Optionally update this file's environment variables table

---

## Troubleshooting

**ModuleNotFoundError when starting a service:**
- Set `PYTHONPATH` correctly (see [PYTHONPATH Gotchas](#pythonpath-gotchas))
- Run `pip install -r backend/requirements.txt` again

**Import error with multiple `app` packages:**
- Never run `pytest backend/ scripts/` in one command
- Always run component tests separately (see [Common Commands → Run all tests](#run-all-tests))

**Database connection refused:**
- If using Azure: ask team lead to start the server or run `az postgres flexible-server start --resource-group tax-advisory-rg --name tax-advisory-db-tax`
- Switch to local Postgres: `docker compose -f docker/docker-compose.yml up -d postgres` and set `DATABASE_MODE=local` in `.env`

**Port already in use:**
- `lsof -i :8000` (macOS/Linux) or `netstat -ano | findstr :8000` (Windows) to find process
- Kill and restart, or use a different port (update `.env` / component config)

**Pre-commit hook failures:**
- Run `pre-commit run --all-files` to see what's failing
- Fix code, then re-stage and commit (do NOT amend)

---

## Git & Commits

No special commit conventions beyond clear, descriptive messages. See README.md for git workflow (branch, pull, push, merge from main).

**No `Co-Authored-By` in commits** — commits are attributed to the individual making them.
