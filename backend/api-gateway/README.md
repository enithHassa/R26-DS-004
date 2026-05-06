# API Gateway

Thin async reverse proxy in front of the component services. The frontend only
talks to `GATEWAY_PORT` (default `8000`); the gateway proxies to each component
on its own port.

## Routing

| Prefix                         | Upstream env var             | Status                |
| ------------------------------ | ---------------------------- | --------------------- |
| `/api/v1/recommendation/**`    | `COMP_RECOMMENDATION_URL`    | wired (Component 3)   |
| `/api/v1/transaction/**`       | tbd                          | placeholder           |
| `/api/v1/optimization/**`      | `COMP_OPTIMIZATION_URL`      | wired (Component 2)   |
| `/api/v1/llm/**`               | tbd                          | placeholder           |

`GET /ready` probes `GET {COMP_RECOMMENDATION_URL}/health` and `GET {COMP_OPTIMIZATION_URL}/health`; returns `checks.recommendation` and `checks.optimization` booleans.

## Run

```bash
source .venv-backend/bin/activate
PYTHONPATH=. uvicorn app.main:app \
  --app-dir backend/api-gateway \
  --reload --port 8000
```

Add the `httpx` dependency to `backend/requirements.txt` if it isn't already
present (it is transitively available via FastAPI's TestClient, but for the
running gateway the explicit pin is required).

## Tests

```bash
PYTHONPATH=. pytest backend/api-gateway
```

## Component 2 — Compliance via gateway

With optimization on **8002** and gateway on **8000** (see `../comp-tax-optimization/README.md`):

```bash
curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/optimization/compliance/check" ^
  -H "Content-Type: application/json" ^
  -d "{\"profile\":{\"tax_year\":\"2024_25\",\"employment_type\":\"employee\",\"dependents\":0,\"annual_gross_income\":\"2400000\",\"estimated_annual_taxable_income\":\"1800000\"},\"strategy\":{\"claims\":[{\"relief_code\":\"life_insurance_premium\",\"claimed_amount_annual\":\"50000\"}]}}"
```

Proxied paths are not listed in the gateway Swagger UI (`include_in_schema=False`); use **curl**, the dashboard, or the optimization service’s **http://localhost:8002/docs** for an interactive schema.
