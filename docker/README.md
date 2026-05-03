# Local Docker services

`docker-compose.yml` provides a local Postgres (and optional MLflow tracking
server) so development isn't blocked when the Azure database is stopped to
save credits.

## Start the local DB

```bash
# from repo root
docker compose -f docker/docker-compose.yml up -d postgres
```

Then in `.env`:

```
DATABASE_MODE=local
```

## Run Alembic against local Postgres

```bash
source .venv-backend/bin/activate
alembic upgrade head
```

## Optional: local MLflow tracking server

```bash
docker compose -f docker/docker-compose.yml --profile ml up -d mlflow
```

Set `MLFLOW_TRACKING_URI=http://localhost:5000` in `.env` to log runs there
instead of the local `./mlruns` file store.

## Stop

```bash
docker compose -f docker/docker-compose.yml down
```
