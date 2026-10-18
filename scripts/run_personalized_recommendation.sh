#!/usr/bin/env bash
# Start Component 3 (personalized recommendation) + TaxWise login UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! curl -sf -m 2 "http://127.0.0.1:8003/health" >/dev/null; then
  echo "Starting Component 3 on :8003…"
  export PYTHONPATH="backend/comp-personalized-recommendation:$ROOT"
  .venv-backend/bin/python -m uvicorn app.main:app \
    --app-dir backend/comp-personalized-recommendation \
    --reload --host 127.0.0.1 --port 8003 &
  sleep 2
else
  echo "Component 3 already running on :8003"
fi

if ! curl -sf -m 2 "http://127.0.0.1:8000/health" >/dev/null; then
  echo "Starting API gateway on :8000 (needed for /login)…"
  export PYTHONPATH="backend/api-gateway:$ROOT"
  .venv-backend/bin/python -m uvicorn app.main:app \
    --app-dir backend/api-gateway \
    --reload --host 127.0.0.1 --port 8000 &
  sleep 2
else
  echo "API gateway already running on :8000"
fi

echo "Opening TaxWise login: http://127.0.0.1:5173/login"
cd "$ROOT/frontend"
exec npm run dev:recommendation
