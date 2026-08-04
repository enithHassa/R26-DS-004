# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**AI Tax Advisory System** — a monorepo for final-year research on intelligent, explainable tax advisory.

Four research components:
1. **Component 1** — Transaction Semantic Reasoning (`:8001`)
2. **Component 2** — Tax Strategy Optimization (`:8002`)
3. **Component 3** — Personalized Recommendation (`:8003`)
4. **Component 4** — Intelligent Tax Advisory Language Model (`:8004`)

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

> **Critical:** Never run `pytest backend/ scripts/` together in one command. Multiple packages named `app` live under `backend/`, triggering `ImportPathMismatchError`. Run **three** separate passes:

```powershell
# Scripts (chunking, SQLite, outline helpers)
.\.venv-backend\Scripts\python.exe -m pytest scripts -q --tb=short

# Language-model component
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-language-model/app/tests -q --tb=short

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

All from repo root with `$env:PYTHONPATH = "$PWD"`:

```powershell
# Component 1 — Transaction Semantic (port 8001)
python scripts/run_transaction_semantic_api.py

# Component 2 — Tax Optimization (port 8002)
.\.venv-backend\Scripts\python.exe -m uvicorn tax_opt_b_app.main:app `
  --app-dir backend/comp-tax-optimization --reload --port 8002

# Component 3 — Personalized Recommendation (port 8003)
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend/comp-personalized-recommendation --reload --port 8003
```

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
| `backend/api-gateway/app/main.py` | Router; registers proxy routes for all 4 components |
| `backend/shared/` | DB, settings, schemas, logging, middleware (shared by all components) |
| `backend/comp-language-model/` | Component 4 (LLM); NLU parse, query with citations |
| `backend/comp-tax-optimization/` | Component 2 tax strategy optimization |
| `backend/comp-personalized-recommendation/` | Component 3 recommendations |
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

Multiple packages named `app` live under `backend/`. When running a service or tests, set `PYTHONPATH` to include both:
1. The component directory (so `app/` resolves)
2. The repo root (so `backend.shared` imports work)

Examples:
```powershell
# Language-model component
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/comp-language-model

# API gateway
$env:PYTHONPATH = "backend/api-gateway;$PWD"
.\.venv-backend\Scripts\python.exe -m uvicorn app.main:app --app-dir backend/api-gateway

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

Frontend dev server proxies `/api` to the gateway (configurable in `vite.config.ts` → `VITE_API_BASE_URL`, default `http://127.0.0.1:8000`).

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
1. Create `backend/comp-{name}/app/main.py` (FastAPI entry point)
2. Add `COMP_{NAME}_URL` to `backend/shared/config/settings.py`
3. Register proxy route in `backend/api-gateway/app/main.py`
4. Update `docs/PHASES_RUNBOOK.md` with startup command

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
- If using Azure: ask team lead to start the server or run `az postgres flexible-server start --resource-group tax-advisory-rg --name tax-advisory-db`
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
