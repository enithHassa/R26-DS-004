# AI Tax Advisory System

Standardized monorepo scaffold for final-year research on intelligent, explainable tax advisory.

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

```bash
source .venv-backend/bin/activate

# Component 3 (Personalized Recommendation)
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/comp-personalized-recommendation \
  --reload --port 8003

# API Gateway (proxies /api/v1/recommendation/** to the component above)
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/api-gateway \
  --reload --port 8000
```

```bash
# Dashboard
cd frontend && npm install && npm run dev     # http://localhost:5173
```

## Quality gates

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files                 # ruff + black + mypy + standard hooks

PYTHONPATH=. pytest                         # run all backend tests
cd frontend && npm run typecheck && npm run lint
```
