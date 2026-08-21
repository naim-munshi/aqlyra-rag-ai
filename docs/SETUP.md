# Setup

## Requirements

Recommended local tools:

```text
Docker Desktop
Git
Node.js 24
Python 3.13+
```

## Start the backend services

From the repository root:

```bash
docker compose up -d --build
docker compose ps
```

The normal development stack includes:

```text
postgres
redis
backend
voice-worker
```

Backend URL:

```text
http://127.0.0.1:8000
```

## Check the backend

Health:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
```

Readiness:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/readiness
```

Metrics:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/metrics
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:3000
```

If there is no authenticated session, the root page can redirect to `/login`.

## Run the backend directly

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PostgreSQL and Redis still need to be available.

## Database migrations

Alembic migrations are stored in:

```text
backend/alembic/versions/
```

The Docker backend entrypoint applies migrations during container startup.

## Run backend tests

Tests use a separate PostgreSQL instance.

Database URL:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test
```

Run from `backend/`:

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test' python -m pytest -q
```

Do not use the normal development database for tests.

## Frontend checks

```bash
cd frontend
npm run lint
npm run build
```

## Production Compose profile

Validate the production profile:

```bash
docker compose --profile production config --quiet
```

The production profile contains:

```text
postgres
redis
backend
frontend
voice-worker
alert-worker
caddy
```

Production environment values start from:

```text
backend/.env.production.example
```

The real production environment file must stay out of Git.

## Production preflight

Run:

```bash
scripts/ops/production-preflight.sh backend/.env.production
```

The preflight checks the main production settings, including environment mode, debug, CORS, domain values, secrets, database credentials, Redis, model provider configuration, grounding verification, and rate limiting.

## Persistent data

The normal persistent state includes:

```text
PostgreSQL data
uploaded documents
Caddy state
```

Normal updates should not delete these volumes.

## Backup and restore

Operational scripts live in:

```text
scripts/ops/
```

They cover backup, backup verification, restore, and production preflight.

Backup verification uses temporary restore state so it does not overwrite the live database.

## Stop the stack

```bash
docker compose down
```

Do not remove persistent volumes unless you actually intend to delete the stored data.
