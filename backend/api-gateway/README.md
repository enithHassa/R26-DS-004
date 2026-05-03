# API Gateway

Thin async reverse proxy in front of the component services. The frontend only
talks to `GATEWAY_PORT` (default `8000`); the gateway proxies to each component
on its own port.

## Routing

| Prefix                         | Upstream env var             | Status                |
| ------------------------------ | ---------------------------- | --------------------- |
| `/api/v1/recommendation/**`    | `COMP_RECOMMENDATION_URL`    | wired (Component 3)   |
| `/api/v1/transaction/**`       | tbd                          | placeholder           |
| `/api/v1/optimization/**`      | tbd                          | placeholder           |
| `/api/v1/llm/**`               | tbd                          | placeholder           |

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
