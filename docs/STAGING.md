# Staging validation and release gate

For an Ubuntu ARM64 VM that retains the existing Docker Compose services, see [Oracle Always Free](ORACLE_ALWAYS_FREE.md).

Aqlyra runs behind Caddy -> Next.js -> FastAPI. Do not publicly expose
PostgreSQL, Redis, the FastAPI metrics endpoint, or the backend's port 8000.
The default Compose bindings for PostgreSQL and FastAPI are localhost-only.

## Before deployment

1. Provision a staging host with Docker Compose, DNS pointing to the host,
   and inbound TCP 80/443 (and UDP 443 if HTTP/3 is desired) for Caddy to
   obtain and renew HTTPS certificates. Use a dedicated database and test
   accounts, not production data.
2. Configure `backend/.env.production` using the
   [production template](../backend/.env.production.example), with a
   staging domain and staging-only credentials. Keep the file outside Git.
   Never overwrite an existing private configuration with the template.
3. Run `scripts/ops/production-preflight.sh backend/.env.production`.
4. From the repository root run:
   `docker compose --env-file backend/.env.production --profile production
   config --quiet`.
5. Build the backend, voice-worker and frontend Docker images. GitHub Actions
   validates that these Dockerfiles build successfully. The real deployment
   still needs a fresh frontend build with its configured public Google Client
   ID; do not deploy the example-config CI image.
6. Start staging with
   `docker compose --env-file backend/.env.production --profile production
   up -d --build`, then check with
   `docker compose --env-file backend/.env.production --profile production ps`.

## Native ARM64 pre-deployment CI

The [Native ARM64 Full-stack Predeploy](../.github/workflows/arm64-predeploy.yml)
workflow builds the backend, frontend and voice-worker images on a native
`ubuntu-24.04-arm` GitHub runner. It starts disposable ARM64 PostgreSQL,
Redis, FastAPI, Next.js and Caddy containers and checks:

- non-root native ARM64 application images;
- expected private networking and named data volumes;
- backend migrations and database readiness;
- the public-path health and anonymous authorization checks through Caddy;
- rejection of a malicious cross-origin authentication request;
- a bounded, unauthenticated HTTP p50/p95 and RPS probe.

The workflow also creates disposable database and upload markers, captures
a backup, verifies its archive and temporary-database restore, modifies
both markers, executes the actual restore script with explicit CI-only
confirmation, and verifies the original records/files return. This is
a **destructive test only on ephemeral CI resources** and does not count
as an off-host production recovery rehearsal.

For CI **only**, Caddy uses `http://localhost` with local test settings and
deterministic AI providers. No Internet-facing service, user data or paid
model API is involved. Consequently, passing this job does **not** verify
live TLS certificate issuance, Google login, SMTP, real model responses,
voice-provider integration, backup restoration, OCI VM performance, or
the full end-to-end user workload.

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

## Performance baseline (authorized staging only)

After the HTTPS security smoke check passes, run the
[bounded transport performance probe](PERFORMANCE_BASELINE.md).
It measures p50/p95 response time and errors using up to 100
**unauthenticated GETs** and 4 concurrent requests; it does not call
AI models, use API credits, or establish RAG concurrency limits.

Deployment CI now checks Compose's network exposure, least-privilege
application containers, PostgreSQL and upload persistence, and
shared uploads for API and voice workers. Unit tests deliberately
exercise unsafe configurations and must fail closed.

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

## GitHub main branch protection (owner-only setting)

The [Always-on Merge Gate](../.github/workflows/merge-gate.yml) runs on
**every** pull request to `main`, including documentation-only changes.
It checks offline security tests, operational scripts, Markdown links,
and the production Compose network/storage contract. This makes it a
safe **required status check**: path-filtered CI jobs cannot be
required for all PRs because some changes do not trigger them.

**Repository owner action (cannot be completed by this connector):**

1. Open **Settings → Rules → Rulesets → New branch ruleset** in GitHub.
2. Give it the name `Protect Aqlyra main`, set enforcement **Active**,
   and target the `main` branch.
3. Enable **Require a pull request before merging**, **Require status
   checks to pass**, **Block force pushes** and **Restrict deletions**.
4. Choose exactly `Always-on Merge Gate` as the required job after
   it has run successfully. Optionally require conversation resolution.
5. As a solo developer, do not require one external approval unless a
   separate reviewer is available. Review the rule before saving so
   the repository owner does not lock out their own merge workflow.
6. Confirm `main` is protected; no rule is considered active until
   GitHub reports it as such.

For changes to code, inspect the additional backend, frontend,
dependency-audit and native ARM64 checks before merging. Some of these
workflows use path filters and therefore are **not** guaranteed to
appear on documentation-only pull requests.

## Release and rollback

Record the deployed Git SHA, Docker image digests, current Alembic revision,
and the timestamp/location of the latest verified off-host backup. Before
deploying a migration, rehearse its forward and recovery behavior on staging.

Deploy by pinned, reviewed commits, not by force-pushing `main`.
GitHub `main` branch protection was not enabled as of this audit; configure
the required CI status checks and merge policy before an unrestricted
production release. On a release
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

## Application container privilege boundary

The backend (including migrations and alert worker), voice worker, and
frontend run as unprivileged users. Compose drops Linux capabilities and
prevents privilege escalation for these application services. PostgreSQL,
Redis, and Caddy retain their upstream container configurations.

**Existing deployments:** before introducing this backend image, verify
that the current uploads Docker volume is writable by UID 10001. Uploads
created by the previous root process may require a one-time ownership
migration in a maintenance window. First take and verify a backup; never
remove the persistent uploads or database volumes. On new Docker volumes,
`/app/uploads` ownership is provisioned by the image. Production volume
permissions still require testing on the actual staging server.

## CI fresh-volume startup check

In addition to building Docker images and inspecting their non-root user
IDs, the deployment workflow now starts a fresh PostgreSQL + Redis + API
stack with non-production test credentials. It waits for the backend
readiness endpoint after the automatic migrations and verifies that the
persistent upload volume is writable. This is an ephemeral GitHub Actions
smoke check, not a substitute for running the same procedure against an
existing staging volume containing migrated user documents.
