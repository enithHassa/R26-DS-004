# Personalized Recommendation & Predictive Impact Modeling

Component 3 of R26-DS-004. FastAPI service that owns user financial profiles,
tax strategy generation, learning-to-rank recommendations, and Monte Carlo
predictive impact simulation.

## What lives here (Component 3 only)

```
app/
├── main.py              # FastAPI app factory + lifespan
├── deps.py              # shared dependencies (DB session, auth)
├── config.py            # COMP_RECOMMENDATION_* settings (rules path, artifacts, weights)
├── schemas/             # Component-3 Pydantic contracts (FR1–FR10)
│   ├── profile.py           # FR1, FR2
│   ├── strategy.py          # FR3, FR4
│   ├── recommendation.py    # FR5, FR6, FR9, FR10
│   └── impact.py            # FR7, FR8
├── routers/             # HTTP routes grouped by resource
├── services/            # Business logic (filled phase-by-phase)
├── models/              # SQLAlchemy ORM models (Phase 2 / WP4)
└── tests/
```

## What lives in shared space (used by every component)

| Shared path                              | Purpose                                     |
| ---------------------------------------- | ------------------------------------------- |
| `backend/shared/config/settings.py`      | DB, gateway ports, CORS, MLflow URI         |
| `backend/shared/config/database.py`      | SQLAlchemy engine + `Base` + `get_db`        |
| `backend/shared/schemas/common.py`       | Generic primitives only (Currency, RiskTolerance, pagination, errors) |
| `backend/shared/utils/logging.py`        | loguru configuration                        |
| `backend/api-gateway/`                   | Reverse-proxy gateway                       |
| `frontend/src/components/ui/**`          | shadcn primitives                           |
| `frontend/src/components/layout/**`      | App shell                                   |
| `frontend/src/lib/api-client.ts`         | Axios factory                               |

Do not put Component 3 code in any of the paths above. Everything personalized-
recommendation-specific belongs in `backend/comp-personalized-recommendation/`,
`models/personalized-recommendation/`, or `frontend/src/features/personalized-recommendation/`.

## Run locally

```bash
source .venv-backend/bin/activate
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/comp-personalized-recommendation \
  --reload --port 8003
```

Open:
- Swagger UI: http://localhost:8003/docs
- Health: http://localhost:8003/health
- Readiness: http://localhost:8003/ready

## Tests

```bash
source .venv-backend/bin/activate
PYTHONPATH=. pytest backend/comp-personalized-recommendation
```
