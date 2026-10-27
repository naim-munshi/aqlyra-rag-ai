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

**Status:** only code/docs/test progress; no Neon/Vercel/Redis/Resend
resource has been provisioned for Aqlyra. Phase 2 is IN PROGRESS.
The prior disposable ARM64 CI full-stack is real but not a
persistent public HTTPS staging host.
