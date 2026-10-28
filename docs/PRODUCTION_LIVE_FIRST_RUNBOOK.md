# Aqlyra — controlled production-first launch (owner preference, 2026-10-28)

**Decision:** owner prefers deploying the **main website** and testing against
that deployed origin, instead of maintaining an extra `aqlyra-preview`
Neon child branch. This is a deployment plan, **not authorization to bypass
required security and data-integrity gates**, and not proof of public launch.

## Exact targets and current state

- Source: `naim-munshi/aqlyra-rag-ai`; core-only candidate PR #36 from
  `release/core-without-study-abroad-20261027`. Study Abroad stays excluded.
- Vercel project: existing `aqlyra`, Hobby team. No deployment or domain
  verified as live. Production env keys explicitly set:
  `NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED=false` and
  `NEXT_PUBLIC_AQLYRA_DEMO_ONLY=false`. These are feature flags only;
  `BACKEND_API_URL` is not configured. Project Vercel Auth covers deployment
  URLs; verify actual access controls before any URL is shared.
- Neon: separate Free `aqlyra-staging`, ID `rough-river-66110449`,
  Singapore PostgreSQL 18; its default branch happens to be called
  `production`. User-supplied console view confirms
  `private-documents` has visibility `Private`, not that API credentials,
  read grants, upload CORS or user isolation work. Use this disposable
  project for initial limited-access launch, **never an existing unrelated
  production database**.
- Render: no Aqlyra backend service yet. Existing unrelated
  `sakuraglam-private-preview` is out of scope. Render Free lacks persistent
  disk and sleeps after inactivity. Never store uploaded bytes on its disk.
- Neon MCP tool project scope is incorrectly a GitHub repository URL. Do
  not call mutating Neon tools until the connected scope is the actual ID.

## Phase 2 — provider prerequisites before first production build

1. Verify the selected Vercel Hobby usage is **non-commercial/personal**.
   Do not launch a commercial company service under Hobby. Confirm a
   compliant plan separately before commercial monetization or operation.
2. Obtain least-privilege project/branch-scoped Neon DB + S3 credentials
   **inside provider secret dashboards**. Never copy secrets into Git,
   tickets, screenshots, CI logs or chat. Use a **direct** DB connection
   for pgvector/Alembic and dumps; app runtime uses pooled DB connection.
3. Configure isolated Render backend on the expected branch with auto
   deploy OFF, `DATABASE_MIGRATION_MODE=manual`,
   `PRIVATE_OBJECT_STORAGE_ENABLED=false`,
   `CLOUD_UPLOAD_PUBLIC_ENABLED=false`, and all security production
   defaults ON. Require usable Redis over TLS, HTTP-based verified email
   delivery, real LLM/embedding provider credentials and memory budget
   confirmation. Use production quality providers; deterministic stubs
   are forbidden in production.
4. Back up the empty/disposable Neon instance and independently prove
   restore into a separate isolated target. Then run reviewed migrations
   (`CREATE EXTENSION IF NOT EXISTS vector`, `alembic upgrade head`)
   against this project **only**. Code CI already checks PostgreSQL 16
   and 18; it cannot substitute for real Neon SQL verification.
5. Configure Vercel server-only `BACKEND_API_URL` to exact HTTPS Render
   `/api/v1`; set exact backend `CORS_ORIGINS` to deployed Vercel
   origin. Never use wildcard origins or NEXT_PUBLIC backend credentials.
   Keep production cloud uploads disabled.

## Phase 3 — deploy main site with restricted access and test there

1. Require green exact-head CI, independent PR review and explicit owner
   approval of protected `main` merge. If using an approved staging
   production build, track its exact commit and do **not** bypass main
   protection merely to avoid review.
2. Deploy the selected commit to Vercel **Production** and Render backend,
   first with Vercel Authentication/restricted access on every reachable
   domain. A protected production deployment is still a production-target
   deployment, without exposing unfinished login/uploads to the public.
3. Smoke-test real backend `/api/v1/health` and readiness, real login/email,
   account A/B isolation, file upload/finalization/restart persistence,
   signed object grants, document delete/replay cleanup, RAG retrieval
   grounding, AI-file export, admin authorization and rate-limiting.
   Verify no client-visible secrets, run migration/backups and restore,
   exercise rollback and fail-closed provider outages. Keep redacted
   timestamped PASS/FAIL evidence.
4. Only after checks pass may the owner approve disabling deployment
   access restrictions and enabling specific cloud features.
   Never automatically enable cloud upload or public read on the private
   bucket. Run security checks periodically after public opening.

## Immediate BLOCKERS (not optional)

- Neon project-scoped management access or operator-provisioned credentials
  must be available before migration/backend config. The existing incorrect
  connector scope cannot be bypassed with an arbitrary project ID.
- No Render Aqlyra service, backend env secrets, active Redis, email sender,
  model quota or Vercel `BACKEND_API_URL` have been independently verified.
- Existing CI success is necessary but does **not** prove live HTTPS
  usability, off-host restoration, RAG quality or public security.
- Vercel Hobby and Render Free are not a reliable platform for a public
  commercial always-on service; select compliant/production-capable
  hosting before promising public commercial SLAs.

**No production deployment, public-domain enablement, secret creation,
GitHub protected-branch merge or live database migration is performed
by committing this file.**
