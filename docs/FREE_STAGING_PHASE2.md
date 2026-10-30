# Phase 2 free-only staging — disposable CI acceptance

**Project:** Aqlyra RAG AI, GitHub [scoped core PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36).
**Study Abroad is deferred.** Preserve README, FastAPI, Next.js,
PostgreSQL/pgvector, Redis, private uploads and all RAG/identity behavior.

## Actual status / constraints

No persistent free external hosting environment has been verified for
this full application. **Do not treat a public frontend-only demo as the
authenticated Aqlyra system.**

Read-only account discovery on 2026-10-27:

- **Railway Aqlyra-Staging:** no live deployment. Backend/frontend
  pinned to the scoped core branch, pgvector and two volumes are
  **staged only**, but Redis creation was denied under Free resource
  limits. Railway persistent volumes are root-owned and require a
  separate, verified approach to maintain unprivileged UID 10001.
  Keep this configuration staged; do not accept/deploy or upgrade.
- **Render:** the account has a SakuraGlam service, not an Aqlyra
  deployment. Official docs:
  https://render.com/docs/free
  confirm Free web services have ephemeral filesystems, cannot
  attach persistent disks, sleep after idle, and cannot send SMTP
  via TCP ports 25/465/587. A Render Free full Aqlyra backend
  would lose private uploads; do not deploy a misleadingly functional
  login/RAG service with this storage.
- **Supabase:** two already-active user projects exist. Official docs:
  https://supabase.com/docs/guides/platform/billing-on-supabase
  cap the Free plan at two active projects per user. We have **not**
  touched existing tables, auth or storage. Do not repurpose an
  existing application database without the owner's explicit choice.
- **Vercel Hobby:** suitable for a personal frontend walkthrough,
  but a frontend-only build cannot replace FastAPI, pgvector, Redis,
  private uploads, workers or SMTP. \`aqlyrax\` is a separate demo
  project and must not be mistaken for the real Aqlyra release.

Do not use root permission, ephemeral uploads, production data,
public database/Redis ports, unsupported free quota workarounds,
plan upgrades or surprise billing.

## Available $0 acceptance path (already working in GitHub Actions)

Run the existing **Native ARM64 Full-stack Predeploy** GitHub Actions
workflow, expanded with the script
\`scripts/ops/ephemeral_fullstack_e2e.py\`.

The job launches real Docker Compose PostgreSQL/pgvector, Redis,
FastAPI, Next.js and Caddy **only inside a disposable GitHub runner**.
It now tests additional HTTP calls against the *actual* FastAPI server:

1. Anonymous access is denied and the deferred Study Abroad route 404s.
2. Two independent synthetic test users register, log in and receive
   separate sessions using a test-only temporary env file with
   \`EMAIL_VERIFICATION_REQUIRED=false\`.
3. One user creates a private conversation. The second user gets 404.
4. Upload Markdown, parse/index embeddings in pgvector, read actual
   uploaded content. The other user cannot fetch it.
5. Owner-scoped pgvector retrieval returns their document; the other
   user sees no foreign hits even when its ID is supplied.
6. Deterministic RAG produces citations to the owner's document;
   another account receives a safe refusal with no citations.

No personal files, real provider tokens, external database, email or
billing are needed. No test bypass is committed into production code:
the CI runner writes a private temporary copy of \`backend/.env.example\`
with verification disabled **only for disposable container startup**,
never to the repository or deployed infrastructure.

### Run it manually

In the GitHub repository, go to
[Actions → Native ARM64 Full-stack Predeploy](https://github.com/naim-munshi/aqlyra-rag-ai/actions/workflows/arm64-predeploy.yml)
and run it on the scoped core branch, or trigger CI via a PR commit.
The script intentionally refuses any non-loopback URL, so it cannot
write synthetic account data to a public staging or production host.

### Safety and limitations

A PASS proves live in-run HTTP requests across FastAPI, real temporary
PostgreSQL/pgvector, files and deterministic AI. It does **not** prove:
persistent hosting, external TLS, real SMTP/Google OAuth, real LLM
accuracy, Arabic/Bangla document rendering, long-term off-host
backups, background workers, or production privacy compliance.

The GitHub runner and all data are disposed of at the end of the job.
This is **free ephemeral integration acceptance** — Phase 2 still
needs a real, independently verified HTTPS staging host with secure,
persistent uploads before it can be called completely finished.

Keep the active GitHub main Ruleset and independent PR review intact.
Do not merge PR #36 or deploy production just because this synthetic
test passes; follow \`docs/RELEASE_ACCEPTANCE.md\`.
