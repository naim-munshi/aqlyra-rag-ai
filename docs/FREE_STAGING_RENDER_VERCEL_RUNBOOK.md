# Aqlyra Phase 2 — $0 noncommercial staging deployment runbook

**Not production.** This runbook covers the unmerged **core-only** PR #36,
`release/core-without-study-abroad-20261027`, preserving the existing
FastAPI/pgvector architecture and README. Study Abroad stays excluded.
No provider has been deployed by committing this file.

## Verified cost and feasibility

| Layer | $0 selection | Acceptance caveats |
| --- | --- | --- |
| Next.js frontend | Existing Vercel Hobby `aqlyra` | Protected preview only; noncommercial; no live deployment |
| FastAPI | Render Free web service (Singapore) | 512 MiB RAM; sleeps 15 min idle; no background worker; ephemeral disk |
| PostgreSQL/pgvector + objects | Isolated Neon Free project + private bucket | 1 GiB Postgres and 5 GiB object allowance/project; branch scoped; current account app connection **fails** |
| Redis | Upstash Free | 256 MiB, 500K commands/month; cannot assume unlimited background queue |
| Verification email | Resend Free | 3K/month, 100/day; sender verification required |
| Model inference | Groq free developer limits + Hugging Face quota, **only if provider grants access** | Not guaranteed free/reliable, HF embedding compute can exceed Render 512 MiB; run real RAG eval before release |

Do not use Render Free PostgreSQL: it expires after 30 days. Do not use
Render Free local filesystem for uploads or user data. Do not accept the
existing 56 staged Railway resource changes: Railway billing and credits
cannot be proven $0 for 24/7 use. No Vercel Hobby commercial launch.

Source verification (2026-10-27):
- https://render.com/docs/free
- https://vercel.com/docs/plans/hobby
- https://neon.com/blog/neon-free-plan-1-gb-per-project
- https://upstash.com/pricing/redis
- https://resend.com/pricing

## Verified staging account inventory (2026-10-28)

- The **new disposable Neon Free** project is named `aqlyra-staging`
  (project ID `rough-river-66110449`, Singapore, PostgreSQL 18).
  User-provided Neon project overview confirms this project's existence.
  It shows one **default branch named `production`**; that branch name is
  Neon-generated and does **not** authorize application production use.
  Do not treat the name as approval to migrate or populate real data.
- Neon overview displayed **0 KB** object storage usage. **This does not
  establish that a private bucket, access credentials, or storage CORS
  are correctly provisioned.** Verify all three before enabling uploads.
- Neon ChatGPT management actions are currently mis-scoped: requesting
  project `rough-river-66110449` is rejected because the connection scope
  is the GitHub repository URL, not a Neon project ID. Omitting project ID
  fails validation. No Neon schema or bucket action was performed.
- Vercel project `aqlyra` is accessible, with no live deployment.
  Branch-specific **Preview only** environment variable
  `NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED=false` was created and verified on
  `release/core-without-study-abroad-20261027`. No production target
  environment variable was changed.
- Render Free workspace currently contains only the unrelated
  `sakuraglam-private-preview` service. Do **not** repurpose it.
  No Aqlyra backend service has been created yet.

Before preview: inspect the Neon project's Storage page to **confirm a
private `private-documents` bucket exists**, create it manually only if
missing, and verify the branch-specific credential scope. Do not use public
read access. Set exact origin-limited CORS for signed browser PUT after a
protected preview URL exists. Handle secrets solely in provider dashboards,
never in PRs, chat messages, screenshots or CI logs.

**PostgreSQL 18 gate:** GitHub Backend Tests on this PR must pass using
both `pgvector/pgvector:pg16` and `pgvector/pgvector:pg18` containers;
a successful PostgreSQL 16-only run is not sufficient evidence for the
new PostgreSQL 18 Neon staging project. The real Neon migrations remain a
separate manual acceptance gate after isolated backup/restore rehearsal.

## Exact prerequisites before any preview

1. **Neon:** connect a personal Free account in a supported object
   region (`us-east-2`, `us-east-1`, `eu-central-1`,
   `ap-southeast-1`). Create **new Aqlyra staging** project and branch
   with a **private** 5 GiB-bounded bucket. Use private branch-scoped
   `storage:read`+`storage:write` credentials. Never use another
   project's database, bucket, or parent production branch.
2. **Upstash:** create a Free Redis database, configure TLS
   (`REDIS_URL=rediss://...`). Ensure data is disposable/cache-only,
   never the only persisted job or conversation record.
3. **Resend:** verify a sender domain; create HTTP API key, sender name
   and address. Render Free does **not** support outbound SMTP ports
   25/465/587, so use the existing `EMAIL_DELIVERY_PROVIDER=resend`.
4. **Model:** create development-only provider tokens for the chosen
   RAG providers. Limit token usage and log costs. Do not claim real
   RAG accuracy from deterministic test providers.
5. **Render:** import `deploy/render-free-staging.yaml` only after
   the above sources are ready. It requests **one `plan: free`**
   service, disables auto-deploy, requires private environment secrets,
   and never includes PostgreSQL/volumes/paid workers. Verify the
   dashboard plan is Free and no paid add-on/credit card usage is
   enabled before triggering a deploy. Model/dependency memory and
   cold starts may still prevent the full backend from running.
6. **Schema:** back up the isolated staging DB (and test restoring it)
   before initial install/migration. The Render container sets
   `DATABASE_MIGRATION_MODE=manual` and therefore **does not run
   CREATE EXTENSION or Alembic on container boot**. Operator-run
   `CREATE EXTENSION IF NOT EXISTS vector;` and
   `alembic upgrade head` against the **staging URL only** after
   checking `current`, `heads`, and recording the target schema.
   Do **not** run this against the existing production DB.
7. **Vercel:** keep `main` tracking and production untouched.
   Set server-only `BACKEND_API_URL=https://<staging-backend>/api/v1`
   in Preview **only**. Keep Vercel Authentication on. No
   `NEXT_PUBLIC_*` secret keys. The backend must allow only its
   exact trusted Vercel Preview origin; avoid wildcard CORS.

## Security launch gates

At initial deployment all of these stay **false**:
```text
PRIVATE_OBJECT_STORAGE_ENABLED=false
CLOUD_UPLOAD_PUBLIC_ENABLED=false
NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED=false
BROWSER_AGENT_ENABLED=false
```

Only after the Neon private bucket's CORS (origin, PUT and
`Content-Type` header) and signed PUT/GET grants are verified,
enable `PRIVATE_OBJECT_STORAGE_ENABLED` on **staging only**.
Do not enable both upload flags until full final-object reconciliation
and two-user lifecycle acceptance are PASS. The new CLI
`python -m app.ops.cloud_stage_cleanup` is read-only by default; its
destructive `--apply` mode requires explicit confirmation and should
never run on an unreviewed production bucket.

## Document deletion and delayed stage replay guard (unmerged code)

An authenticated cloud Document delete now requires owner-scoped SQL
linkage and remote deletion of **both** the stage and final objects before
the Document transaction commits. If either remote operation fails, the
metadata remains for an idempotent retry (no 204 success). The deletion
transaction records `cloud_upload_intents.deleted_at` via additive
Alembic revision `b5e4a019dc72` and removes the Document linkage.
It does **not** mark `stage_deleted_at` prematurely.

The original 120-second signed PUT may be replayed even after an
immediate stage deletion. Consequently, the operator-only stage sweep
re-deletes tombstoned staging keys only after `expires_at + grace`.
Normal completed rows require a matching live Document binding; orphaned
inconsistent rows remain quarantined for manual investigation. Failed
remote deletion and commit ambiguity must always be retried or escalated.

**Operator acceptance requirement:** after restoring a disposable DB,
apply and inspect the new migration manually; finalize a test file, delete
it within the PUT TTL, replay the staging PUT, then execute a bounded
cleanup **after** expiry/grace. Verify no staging/final objects remain,
Document metadata is gone, owner B cannot access A, and repeated deletion
or failed S3 operations fail safely. Never enable a scheduled destructive
sweep in free hosting before real-provider evidence and operator review.

## Durable promotion and concurrent recovery safety

Promotion reserves a unique final-object key in the SQL upload intent
**before** remote writes. When remote PUT has succeeded but verification
returns a transient error, the reserved final object MUST NOT be
compensating-deleted: a separate recovery worker may have already
verified and linked those bytes in the same owner-scoped SQL transaction.
The final key remains for `recover_promoted_cloud_document`, which
rehashes the existing remote bytes before any Document metadata commit.
Unreserved, standalone promotion calls retain their best-effort cleanup.

Regression coverage: provider final-read failure, corrupted verification
response, failed PUT, no destructive DELETE for reserved keys, and a
subsequent successful owner-bound recovery without another PUT. **Do not
interpret a transient verification error as proof of an orphan.** Cloud
object GC still requires a separate read-only orphan audit and independent
staging acceptance; no automatic final-key deletion is enabled.

## Mandatory end-to-end test

Run **independent test accounts A and B**, both email-verified:
- Register/login/reset/verify via real Resend, no leaked tokens/log data
- Stage 1 KiB and 25 MiB files, private PUT, SHA256 finalization,
  DB commit, document processing, retrieval/citations and verified
  private download (without Vercel body proxy)
- B cannot see, finalize, retrieve or delete A's private objects; 403/404
- Expired/replayed grants, duplicate documents, malformed PDF/OOXML,
  SQL disconnect, bad remote checksum, cold starts and signed PUT replay
- Delete/reprocess/restore, after 15-minute sleep and provider restarts,
  verify Document metadata/object consistency and role boundaries
- Private object orphan audit and stage cleanup dry-run, safe rollback
- Off-host encrypted Postgres and object backups, actual **restore** to
  a separate disposable branch without overwriting unrelated accounts
- Real-provider RAG grounding evaluation and memory/CPU consumption

Save evidence under a redacted `reports/staging/` manifest. No chat
content, IPs, API keys, signed URLs, DB URLs, or personal email addresses.

## Stop conditions

- API/DB/storage provider account unavailable or credentials absent
- Paid plan/trial requested without explicit approval
- Backend exceeds Render Free 512 MiB RAM or cannot serve a complete
  25 MiB test within reasonable resource constraints
- Private bucket CORS or provider presigning differs from assumptions
- Persistent worker not available and recovery cannot be executed
- No independently verified off-host backup/restore
- All 7 GitHub workflows not PASS on exact PR head
- Independent review missing; repository `main` protected

**State:** Phase 2 IN PROGRESS. New isolated Neon Free project
exists, but no real schema migration, bucket credential verification,
Render/Vercel staging deployment, or two-user acceptance has occurred.
Neon ChatGPT connector remains mis-scoped to a GitHub URL; repository
CI cannot substitute for provider-owned prerequisites.
