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

From the repository root, create the private local settings file first,
then start the required services:

```bash
cp -n backend/.env.example backend/.env
docker compose --env-file backend/.env up -d --build postgres redis backend
docker compose --env-file backend/.env ps
```

Review the untracked `backend/.env` before use. Replace placeholder secrets
and add real SMTP credentials to test verified email registration. The
development template uses deterministic LLM and embedding providers; this is
not a substitute for testing real model providers.

The optional `voice-worker` requires LiveKit credentials. Start it separately
only when the voice integration is configured:

```bash
docker compose --env-file backend/.env up -d --build voice-worker
```

The production profile adds the frontend, alert worker, and Caddy.


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
npm ci
cp -n .env.example .env.local
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:3000
```

If there is no authenticated session, the root page can redirect to `/login`.

## Verified login setup

New email/password accounts must verify a six-digit code before they
can receive an Aqlyra session. Google sign-in uses the same internal
session after the backend verifies the Google ID token.

### Gmail sender

Use a dedicated Gmail account or your own Gmail account for local and
portfolio deployments:

1. Enable 2-Step Verification on the Google account.
2. Create a [Google App Password](https://support.google.com/mail/answer/185833) for Aqlyra.
3. Remove spaces from the displayed App Password.
4. Put the values in `backend/.env`; never commit that file.

```dotenv
EMAIL_VERIFICATION_REQUIRED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your-account@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM_EMAIL=your-account@gmail.com
SMTP_FROM_NAME=Aqlyra
SMTP_USE_SSL=true
```

Do not use the normal Gmail account password as `SMTP_PASSWORD`.

### Google sign-in

Create an [OAuth 2.0 Web Client ID](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid) in Google Cloud. Add the frontend
origins used by the deployment, including the local origin when
developing:

```text
http://localhost:3000
http://127.0.0.1:3000
```

Put the same public Client ID in both backend and frontend config:

```dotenv
# backend/.env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

```dotenv
# frontend/.env.local
BACKEND_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

For a production Docker frontend build, set `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
in `backend/.env.production` to the same public value as `GOOGLE_CLIENT_ID`.
Docker Compose passes it to the frontend build.

The Google Client ID is public configuration. A Google Client Secret
is not used by this ID-token sign-in flow and must not be exposed to
the browser.

## Run the backend directly

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The process reads `backend/.env` when started from `backend/`. The
`DATABASE_URL` should use `localhost`, not the internal Docker hostname
`postgres`. The command above applies Alembic migrations before
serving the backend. PostgreSQL must be running; Redis is required when
`RATE_LIMIT_ENABLED=true`.

## Database migrations

Alembic migrations are stored in:

```text
backend/alembic/versions/
```

The Docker backend entrypoint applies migrations during container startup.

The verified-identity migration marks existing users as verified so
an upgrade does not lock out accounts created before OTP support.

## Run backend tests

Tests mutate and recreate their database state. Run them against a
**dedicated PostgreSQL 16 test database**, never the normal development or
production database. For example, from the repository root:

```bash
docker run -d --rm --name aqlyra-test-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=aqlyra_rag_ai_test \
  -p 127.0.0.1:5433:5432 pgvector/pgvector:pg16

# After PostgreSQL reports ready:
docker exec aqlyra-test-postgres \
  psql -U postgres -d aqlyra_rag_ai_test \
  -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

Then run from `backend/` in the virtual environment:

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test' python -m pytest -q
```

To stop the disposable test database:

```bash
docker stop aqlyra-test-postgres
```

GitHub Actions uses the same PostgreSQL/pgvector test isolation, with its
service on port 5432 instead of 5433.

## Frontend checks

```bash
cd frontend
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
```

## Production Compose profile

For **first-time setup only**, copy the production template without
overwriting an existing secrets file. Replace placeholders with real values
and protect the private environment file:

```bash
cp -n backend/.env.production.example backend/.env.production
chmod 600 backend/.env.production
```

Edit the file for your real domain, credentials, Google public Client ID,
SMTP, model provider, and (when enabled) voice and alert integrations.
Run the production preflight before starting the stack. Do not commit
`backend/.env.production` to Git. The backend, frontend, and voice images
must be built with the deployment's actual settings, not CI placeholder
configuration.

Validate the production profile:

```bash
docker compose --env-file backend/.env.production --profile production config --quiet
```

Start the stack only after preflight and configuration checks pass:

```bash
docker compose --env-file backend/.env.production --profile production up -d --build
docker compose --env-file backend/.env.production --profile production ps
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

Normal updates should not delete these volumes. Application containers
run as non-root users; if upgrading an existing deployment, verify that the
persistent uploads volume is writable by UID 10001 before replacing the
running containers. See [Staging](STAGING.md) for the migration warning.

## Backup and restore

Operational scripts live in:

```text
scripts/ops/
```

They cover backup, backup verification, restore, and production preflight.
For production, always point operational scripts at the production environment
file rather than the development default:

```bash
AQ_ENV_FILE=backend/.env.production scripts/ops/backup.sh
AQ_ENV_FILE=backend/.env.production scripts/ops/verify-backup.sh backups/<timestamp>
```

Backup verification uses temporary restore state so it does not overwrite the
live database. Backup archives contain private documents and database records:
keep them access-restricted, encrypted at rest, and stored off-host.

Restoring replaces current data. Only use `scripts/ops/restore.sh` after a
verified backup and a planned maintenance window. Test the full recovery
procedure on staging before production launch.

## Stop the stack

For development:

```bash
docker compose --env-file backend/.env down
```

For a configured staging/production profile:

```bash
docker compose --env-file backend/.env.production --profile production down
```

Neither command deletes named volumes. **Never use `down -v` on a
persistent environment.** Backups and restores are operationally disruptive
and should be rehearsed on staging; see [Staging](STAGING.md).
