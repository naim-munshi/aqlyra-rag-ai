# Staging validation and release gate

Aqlyra runs behind Caddy -> Next.js -> FastAPI. Do not publicly expose
PostgreSQL, Redis, the FastAPI metrics endpoint, or the backend's port 8000.
The default Compose bindings for PostgreSQL and FastAPI are localhost-only.

## Before deployment

1. Provision a staging host with Docker Compose, DNS, and a working HTTPS
   certificate. Use a dedicated database and test accounts, not production data.
2. Configure `backend/.env.production` with production-style settings, a
   staging domain and staging-only credentials. Keep the file outside Git.
3. Run `scripts/ops/production-preflight.sh backend/.env.production`.
4. Run `docker compose --env-file backend/.env.production --profile production
   config --quiet`.
5. Build the backend, voice-worker and frontend Docker images. GitHub Actions
   validates that these Dockerfiles build successfully. The real deployment
   still needs a fresh frontend build with its configured public Google Client
   ID; do not deploy the example-config CI image.
6. Start staging and verify service health with
   `docker compose --env-file backend/.env.production --profile production ps`.

## Public endpoint smoke test

After HTTPS is serving on the staging hostname:

```bash
python3 scripts/ops/staging_smoke.py --base-url https://staging.example.com
```

The smoke test is read-only and fails closed if:

- the Next.js health proxy is not ready or is cached;
- the login page is unavailable or lacks Caddy security headers;
- unauthenticated user/session and conversation endpoints do not return 401;
- internal FastAPI metrics are publicly reachable through the frontend.

TLS certificates are validated by Python's standard HTTPS client. The checker
never sends credentials. HTTP is accepted only for loopback test servers when
`--allow-http-loopback` is explicitly set.

## Manual end-to-end checks

Use test accounts only. Verify:

- email registration, expiring OTP, login, logout, and Google sign-in;
- a private PDF/DOCX upload, parsing and vector indexing;
- a grounded answer with citations; unknown evidence must refuse;
- cross-user document, conversation, and memory isolation;
- streaming chat, image attachments, and optional voice sessions;
- Redis failure behavior, app restart, and retained uploaded documents;
- live alert delivery, backup verification and recovery on a disposable copy.

The automated smoke test cannot prove these authenticated or provider-backed
flows work. All must pass before public launch.

## Release and rollback

Record the deployed Git SHA, Docker image digests, current Alembic revision,
and the timestamp/location of the latest verified off-host backup. Before
deploying a migration, rehearse its forward and recovery behavior on staging.

Deploy by pinned, reviewed commits, not by force-pushing `main`. On a release
failure, stop accepting new writes, inspect service health, and restore a
**verified** snapshot when schema or data rollback is necessary. Restoring the
database and upload archive replaces current data and can lose writes since
the backup; do not run restore automatically. Never execute `docker compose
down -v` on a persistent environment.

After successful deployment, rerun the smoke check and manually verify
critical authenticated flows. Promote to production only when all release
checks have recorded evidence.

## Reverse-proxy hardening

Caddy limits incoming request bodies to 32 MB before Next.js parses
multipart data; backend document validation still enforces its 25 MiB file
limit. Validating the Caddyfile is part of deployment CI. Public responses
include basic security headers and HSTS. Confirm these settings on the
actual HTTPS staging domain; do not bypass Caddy with public backend ports.
