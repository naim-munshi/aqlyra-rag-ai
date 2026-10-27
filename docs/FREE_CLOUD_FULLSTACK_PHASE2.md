# Phase 2 — Free cloud migration (core-only, not deployed)

**Scope:** `naim-munshi/aqlyra-rag-ai`, core-only PR #36. Preserve the
existing README, PostgreSQL/pgvector schema, RAG interfaces, document
security and application behavior. Study Abroad stays deferred.

## Selected experimental design

- **Vercel Hobby:** Next.js web frontend and possibly a small Python
  FastAPI Function. Account's existing Vercel project `aqlyrax` is a
  DIFFERENT portfolio demo and must not be edited or reused. Any
  Aqlyra Vercel project must be new, separately named, reviewed and
  deployed on a free personal/noncommercial plan.
- **Neon Free:** an **independent new** private PostgreSQL/pgvector
  project and bucket for uploads. Never use the existing SakuraGlam
  or another application's DB. Neon project/credentials not yet
  connected or provisioned.
- **Upstash Free Redis:** existing redis-py rate limiter may use its
  Redis-compatible TLS endpoint with a `rediss://` URL. Explicitly
  confirm protocol, certificate validation, connection limits and
  rate-limit failure before running production traffic.
- **Resend Free:** HTTPS transactional email for signup and password
  reset. Use `EMAIL_DELIVERY_PROVIDER=resend`, `RESEND_API_KEY`
  (PRIVATE) and `SMTP_FROM_EMAIL` with a Resend-verified domain.
  The existing SMTP mode is the default and remains untouched.

References: https://vercel.com/docs/functions/limitations ,
https://neon.com/docs/guides/serverless-connection-pooling ,
https://upstash.com/docs/redis/help/faq ,
https://resend.com/docs/api-reference/emails/send-email .

## Cloud blockers: required code before a functional deploy

1. **Vercel request and response size**: Function payloads capped at
   4.5 MB; current Aqlyra supports 25 MB uploads and downloads.
   End-to-end private client-to-object-store upload grants,
   validation, checksum/metadata finalization and revocable
   owner-authorized download URLs are needed. DO NOT lower current
   upload limits silently, make buckets public, or try base64 via
   Next.js proxy.
2. **Private storage**: `backend/app/services/storage_service.py`
   currently writes to `UPLOAD_DIR` and parser/renderer work with
   local paths. Implement a carefully tested storage abstraction
   with per-user keys, encrypted private object ACLs, temporary
   local scratch only, safe cleanup and DB/object consistency for
   create, read, process, delete and AI Files exports. Backend
   function filesystem is ephemeral: never treat it as durable.
3. **DB migration**: current `backend/docker-entrypoint.sh` does
   `CREATE EXTENSION vector` and `alembic upgrade head` on
   container startup. Vercel Functions have no such persistent
   entrypoint; migrate exactly once using Neon's **direct**
   connection on an isolated disposable staging database with
   a backup. Serve normal queries from a pooled SSL URL using
   bounded SQLAlchemy connections and `pool_pre_ping`. The core API
   now accepts `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`,
   `DATABASE_POOL_TIMEOUT_SECONDS` and
   `DATABASE_POOL_RECYCLE_SECONDS` without changing existing
   defaults; start at 2/1/10/300 for a small trial and tune using
   measured concurrency. Use `-pooler` only for app traffic, not
   migration/pg_dump. Check permission for `CREATE EXTENSION vector`.
4. **Serverless runtime**: Python function has a 500 MB uncompressed
   bundle limit; current `backend/requirements.txt` contains large
   data tooling. OCR depends on Tesseract language packs installed
   by the Dockerfile, unavailable in the standard Python function.
   Validate package size and move OCR/conversion to an
   independently secured worker before enabling public requests.
   Voice/alert and Browser Agent must stay disabled until
   isolation and event/job-worker architecture are proven.
5. **Security/reliability**: proper rate limits, SMTP-free delivery,
   real secret management, verification, session revocation, two-user
   tests, load and quota monitoring, off-host backups, and privacy
   deletion procedures are required. No production credentials in
   GitHub, logs, screenshots or chat.
6. **Actual acceptance**: only after real HTTPS staging is live,
   test verified domain/Resend email, OAuth, DB and private storage
   under two accounts, RAG with a real provider, Bangla/Japanese
   documents, backup restoration, and 25 MB upload/download.
   No public launch or `main` merge before review and approval.

## Private object storage foundation — implemented but not connected

The opt-in `backend/app/services/private_object_storage.py` adapter
implements branch-scoped private Neon S3-compatible storage primitives:

- Only HTTPS Neon storage endpoints are allowed (prevent arbitrary
  storage endpoint injection); path-style SigV4 and explicit credentials.
- Browser-to-private-bucket presigned `PUT` grants (120-second expiry),
  keys generated from the authenticated owner's UUID plus a random UUID,
  not attacker-controlled filenames; upload limits match the original
  25 MB backend policy.
- Owner/key isolation and bounded streamed retrieval into a temporary
  private file, with complete SHA-256 and content validation before
  parsing; scratch data is deleted on exit/failure.
- Feature flag `PRIVATE_OBJECT_STORAGE_ENABLED=false` by default.
  No client-facing endpoints yet.

**Mandatory before switching the browser upload workflow:** durable
database-backed upload intents with TTL/replay prevention, final-key
promotion that revokes outstanding presigned PUT access, DB/object
transaction recovery and orphan cleanup, authenticated download,
delete and processing/reprocess paths, bucket CORS restricted to
approved frontend origin, real branch-scoped storage keys, and
live 25 MB / two-user / restart tests. Client-facing uploads are
intentionally **NOT enabled** by this foundation.

Official Neon guide:
https://neon.com/docs/storage/get-started (private S3-compatible
buckets and path-style clients). Storage currently supports AWS
Singapore `aws-ap-southeast-1` among documented regions.

## Cloud upload intent ledger (PR branch only, NOT migrated to live DB)

`backend/app/models/cloud_upload_intent.py` and additive Alembic
revision `6ec42b8f19ad` add one **new** `cloud_upload_intents` table;
existing users, documents, RAG embeddings and pgvector tables are unchanged.
The migration has **not been applied to any live database**.

The internal service `cloud_upload_intent_service.py` reserves private
signed staging keys only for **active, email-verified** users, validates
the exact-size/SHA-256 manifest, stores a 10-minute expiring intent,
and atomically changes `issued -> claimed -> completed/failed` using
owner-scoped SQL UPDATE...RETURNING. Expired, foreign, invalid or replayed
claims fail closed, including concurrent requests against the same row.
Credentials and signed URLs are not stored in the table.

**Release gate:** signed `PUT` is valid for 120 seconds but can be
rewritten by the holder until expiry. Before marking completed, server
must stream and verify all bytes and metadata, then promote the file
to a separate immutable owner-scoped key with **no outstanding write
grant** and persist document metadata. Full promotion, crash recovery,
orphan cleanup, authenticated download, AI-file persistence and
worker processing are **NOT implemented**. Therefore there are no
public upload-intent endpoints and private storage flag remains
`PRIVATE_OBJECT_STORAGE_ENABLED=false`.

Do **not** run this migration automatically against the original
production DB or `alembic downgrade`: rehearse on an isolated staging
database, compare schema and verify backup/restore before owner-approved
production release. The migration only creates a table and indexes.

## Private object promotion primitive (not publicly callable)

`backend/app/services/private_object_promotion.py` implements a bounded
internal promotion step after an owner-authorized upload intent is claimed:
it reads the staging object **with size, SHA-256 and magic validation**,
streams the verified bytes into a distinct unpredictable
`final/documents/<owner UUID>/<object UUID>.<extension>` key that has
**never been granted a browser-writable signed PUT URL**, and re-reads
the final key to confirm the size and full SHA-256 hash. It does not
rely on provider ETag checksums. Provider response streams are closed.
On an in-process promotion/verification failure it attempts a
compensating delete of the final key and fails closed. Staging keys
are **retained until an explicit safe cleanup policy is ready**;
no user files are silently deleted.

Unit tests cover two-account isolation, distinct final keys, bad size
and checksum, malformed content, injected storage errors, stream
closing, orphan recovery requirements and guarded deletion.

**Crucial scope:** private storage is still OFF by default. This is
a primitive, NOT an end-to-end finalizer. Promotion does **not**
create a `Document`, complete a `CloudUploadIntent`, persist the
final object key, implement a worker, or guarantee atomic
cross-service writes. Staging keys can be rewritten until their
120-second signature expires, although distinct final keys cannot
be written through that staging URL. Crashes and failed remote
deletion can leave an orphan; a durable reconciliation worker and
DB/object consistency protocol remain mandatory. There is no
public cloud upload API or client-side direct PUT workflow.

## Cloud Document finalization / recoverable SQL binding (PR branch only)

This milestone is an **internal-only implementation**; no cloud upload
HTTP routes are exposed, the private storage feature flag remains OFF
by default, and no real Neon database or object store is changed.

Additive Alembic revision `9ce7a58d230f` extends **only the new**
`cloud_upload_intents` table with nullable `final_object_key`,
`document_id` (unique FK to `documents.id`) and a bounded recovery
index. Existing RAG, `documents`, `document_chunks`, `pgvector`,
memory and user schemas are not altered by this revision.

The private service `cloud_document_finalization.py`:

1. Verifies an active, email-verified owner; atomically claims an
   unexpired intent and stores an unpredictable **final key in SQL
   before remotely uploading** the object. Concurrent claims cannot
   issue two final keys for the same intent.
2. Invokes the verified staging -> private final copy/rehash with that
   persisted final key. No signed browser PUT is issued for a final key.
3. Independently reads and verifies final bytes **again**. Creates a
   matching Document metadata row (using a distinguishable
   `cloud://final/documents/...` location) and updates the claimed
   intent to `completed`, with `document_id`, in **one SQL transaction**.
   Existing duplicate-checksum uniqueness remains enforced.
4. On process failure **after the remote upload but before SQL commit**,
   the claimed intent still contains `final_object_key`. Internal
   `recover_promoted_cloud_document` can reverify bytes and commit the
   missing Document atomically without regranting browser write access.
   Failed/ambiguous commits **must not blindly delete** the final object.
5. Read-only `list_stale_claimed_uploads` locates old claimed intents
   for a future operator-controlled recovery/garbage collection job.
   It does not expose individual user data through any HTTP route and
   does not automatically delete anything.
6. Existing local document process/content/delete API routes explicitly
   **reject cloud:// records with 409** rather than operating on local
   paths or deleting DB metadata while orphaning a remote object.
   These routes remain correct for existing local files.

Tests cover one-time claim, owner isolation, repeated finalization,
cross-account access, duplicate checksum, simulated crash/recovery,
tampered/missing final data, failing S3 writes, safe deletion guards,
read-only recovery scans, and disabled-default behavior.

The old `complete_upload_intent()` helper is intentionally fail-closed:
changing only the intent status to `completed` without a linked
Document is forbidden. Only `commit_verified_cloud_document()` can
complete an intent together with the verified Document insert.

**Release blockers remain:** there is no public grant/finalize API;
no cloud-aware authenticated document download/process/delete path,
no staging key lifecycle/TTL GC, no crash-safe *automated* worker with
leasing/backoff, and no off-host backup or real two-user acceptance.
A `Document` may be linked to cloud bytes in an isolated test but
is deliberately prevented from normal processing/deletion until these
missing paths are implemented. No CI success is proof of live cloud
data durability. Database migrations have **not** been applied outside
ephemeral CI and should not be applied to production without explicit
review, backup, and owner approval.

## Owner-authorized private cloud download (review-only)

New `cloud_document_access.py` verifies that the authenticated
account owns the requested `Document`, that its private final
object key is structurally valid, and that an existing
`cloud_upload_intents` record is `completed`, has the same
owner, `document_id`, key, size, SHA-256 and content type.
Only then can it issue a **45-second presigned private GET**.

The `/documents/{document_id}/content` backend endpoint returns a
no-store, no-referrer 307 redirect to this private grant when
`PRIVATE_OBJECT_STORAGE_ENABLED=true`. For other accounts it returns
404. If storage is not enabled, it returns 409. The Next.js document
API uses `redirect: manual`, accepts HTTPS Neon storage hostnames
only, and forwards the signed redirect directly to the browser.
**The Next.js Function does not buffer or proxy 25 MB downloads.**
Existing local downloads still use their previous streaming route.

This path has tests, but **full cloud uploads, processing and
deletion are NOT enabled for public traffic**. A signed GET URL
confers read access until its short expiry and must not be logged,
shared or included in analytics. The S3-compatible provider must
confirm that `ResponseContentDisposition` and private presigned
GETs work in staging. If a provider's signed requests behave
differently, disable this feature before release.

## Feature-gated browser direct uploads and cloud-aware RAG parsing

This PR adds an **opt-in** direct-upload handshake:

- `POST /api/v1/documents/cloud/prepare` requires a JWT, upload rate
  limit, an active/verified user, a valid filename/size/SHA-256 manifest.
  It writes an expiring owner-specific intent and grants a 120-second
  private signed PUT to the browser.
- Browser code computes SHA-256, uploads up to 25 MiB **directly** to
  the restricted private bucket, then calls
  `POST /api/v1/documents/cloud/{intent_id}/finalize` with JWT via a
  same-origin Next.js proxy. Backend verifies stage/final data and
  atomically returns the linked `DocumentResponse`.
- Document processing uses a bounded temporary local copy after
  owner+intent validation and another SHA-256 check. It deletes scratch
  after parsing and preserves existing embedding/RAG processing.
- Private download uses a 45-second GET redirect instead of passing
  file bytes through Vercel; local upload/read/processing is unchanged.

**These paths are fully disabled for release by default:**
`PRIVATE_OBJECT_STORAGE_ENABLED=false`,
`CLOUD_UPLOAD_PUBLIC_ENABLED=false` (backend), and
`NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED=false` (frontend build). Do NOT
set these true before the deletion/cleanup lifecycle, private-bucket
CORS (only the correct HTTPS application origin and PUT headers),
two-account/25MiB tests, credential isolation, real HTTPS RAG and
backup/restore acceptance. A signed PUT must never be created for a
final key. Audit user-facing `Upload` actions in all UI variants
before enabling it globally.

### External infrastructure evidence

The connected Railway project `Aqlyra-Staging` exists with a
nonproduction `staging` environment and 56 pending configuration
changes for the frontend, backend, pgvector PostgreSQL and
persistent uploads/database volumes. They are all `staged-create`;
**nothing is provisioned or deployed**. The intended branch is
`release/core-without-study-abroad-20261027`.
Railway service billing/credit eligibility is not verified; do not
`accept-deploy` without explicit cost approval. Current staged services
also lack verified external-provider keys and all critical live
secrets. A local Railway pgvector container is an **alternative**
to an independently provisioned Neon database, not a completed
Neon Free deployment.

The Neon account connection cannot list projects (connector tool not
available). No Neon/Upstash/Resend provisioned credentials, live
data or cloud bucket was accessed. Vercel `aqlyra` remains protected
with no deployment. This stage cannot be marked complete from CI alone.

## Work completed on the cloud compatibility branch

A narrow, backwards-compatible **HTTPS email delivery adapter**
is implemented in the FastAPI service. The `smtp` default remains
unchanged. Selecting `resend` uses
`POST https://api.resend.com/emails` with an API key stored
only in the runtime secret manager. Failures raise a sanitized
`EmailDeliveryError`; API responses, one-time codes and secrets
must not appear in error strings or logs. Tests use fake HTTP,
not real user email/paid API traffic. This does **not** establish
real email deliverability; verify a sender domain before staging.

Example staging variables (values must be created by the owner in
the hosting secret manager, not shared here):

```text
APP_ENV=production
EMAIL_DELIVERY_PROVIDER=resend
RESEND_API_KEY=<runtime secret>
SMTP_FROM_EMAIL=<verified sender email>
SMTP_FROM_NAME=Aqlyra
GOOGLE_CLIENT_ID=<staging OAuth client>
REDIS_URL=rediss://<tls redis endpoint>
DATABASE_URL=postgresql+psycopg://<staging pooled endpoint>
DATABASE_POOL_SIZE=2
DATABASE_MAX_OVERFLOW=1
DATABASE_POOL_TIMEOUT_SECONDS=10
DATABASE_POOL_RECYCLE_SECONDS=300
RAG_GROUNDING_VERIFIER_ENABLED=true
BROWSER_AGENT_ENABLED=false
```

**Status (2026-10-27):** The separate Vercel Hobby project `aqlyra`
has been created and connected to `naim-munshi/aqlyra-rag-ai`; Next.js
frontend root is `frontend`. Standard Vercel Authentication protects
preview access. The project has **zero deployments and zero configured
runtime secrets**. Its currently allocated hostname is
`aqlyra-navy.vercel.app`; requested `aqlyra.vercel.app` returned a
Vercel `409 owned-on-other-team` conflict.

**No independent Neon staging database/bucket, Redis/Upstash credentials,
Resend sender or live FastAPI host have been provisioned.** Neon project
management connector currently responds with an unavailable-action
error, so this cannot be treated as working Neon access.

**Phase 2 remains IN PROGRESS:** code, docs and CI do not replace
runtime two-account E2E, provider evaluation, live private object
storage or backup/restore checks. The disposable ARM64 CI full-stack
is real but is not a persistent public HTTPS staging host.
