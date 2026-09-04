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

For a production Docker frontend build, also provide
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` to Compose before running
`docker compose --profile production up -d --build`.

The Google Client ID is public configuration. A Google Client Secret
is not used by this ID-token sign-in flow and must not be exposed to
the browser.

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

The verified-identity migration marks existing users as verified so
an upgrade does not lock out accounts created before OTP support.

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
