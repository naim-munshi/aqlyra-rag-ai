# Security, tenancy, and durable-storage release plan

Status checked: 2026-11-22. This document is an operator checklist, not authorization to change production.

## Current release gates

- The active `aqlyra-main-production-gate` ruleset targets only `~DEFAULT_BRANCH` (currently `main`). It requires one approval, stale-review dismissal, last-push approval, review-thread resolution, strict required checks, and blocks deletion/non-fast-forward updates.
- The backend release branch and frontend release branch are not protected by that ruleset. Add a separate active ruleset targeting both exact release branch names (or a deliberate release/* pattern) before treating them as protected.
- Do not merge the current security PRs until their combined release acceptance and the operator-controlled deployment prerequisites below are satisfied.

## PRs with green CI (not merged)

- #216 multipart ingress limit and atomic document-processing claim.
- #217 auth-epoch revocation for active voice jobs. API and worker must be deployed from compatible revisions together.
- #218 refresh-token families, rotation, replay detection, legacy-cookie upgrade. Requires additive Alembic migration `a1f8c6d2e904`.
- #219 BFF HttpOnly refresh-cookie persistence and read-only Server Component recovery. Must be released together with #218.
- #220 collision-safe LiveKit agent state tempfile.

CI passing is necessary but not equivalent to production acceptance. Keep all PRs unmerged until staging smoke, restore rehearsal, and coordinated API/worker checks are recorded.

## Tenant RLS: do not enable on the current production role

The current API uses a shared SQLAlchemy database connection. The inspected production runtime role was previously identified as having `BYPASSRLS`; policies do not protect rows when the application connects as a bypass role.

Required sequence:

1. Provision a dedicated runtime role with `NOBYPASSRLS`, least-privilege table/sequence grants, and no ownership/superuser privileges. Keep a separate migration owner role for Alembic.
2. Implement transaction-scoped authenticated user context for every API request and trusted worker job. Context must be set only after verifying the user/job identity and must be reset automatically at transaction boundaries.
3. Inventory every user-owned table and relationship (documents, chunks, units, conversations, messages, attachments, projects, memories, embeddings, upload intents, and future organization-owned records).
4. Add RLS policies and composite ownership constraints where cross-table references must remain within one owner/tenant.
5. Test missing context (deny by default), cross-user reads/writes, background indexing, voice worker, cleanup jobs, migrations, and connection-pool reuse on PostgreSQL 16 and 18.
6. Only after staging passes, change the Render runtime DATABASE_URL to the new role. Never change the production role or enable FORCE ROW LEVEL SECURITY without a verified rollback and maintenance plan.

## Durable document storage

- Production local writes are fail-closed unless `LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED` is explicitly enabled.
- The private Neon S3-compatible primitives are present but intentionally not wired into the authoritative upload/finalize flow.
- Do not set the local-durability flag merely because a service is running. Confirm an attached persistent volume or complete the private-object-storage integration first.
- Before enabling remote storage: implement authenticated upload intent, exact owner/key binding, size and checksum verification, transactional DB finalize, idempotent retries, orphan cleanup, and private-only reads.
- Run the synthetic private storage probe; then test upload, download, restart persistence, checksum mismatch, expired intent, tenant isolation, deletion/tombstone, and restore from backup. The probe alone does not certify disaster recovery.
- Do not migrate or delete existing local documents until a verified copy and restore rehearsal exist.

## Multilingual RAG quality

- Keep retrieval changes behind existing feature flags.
- Use a frozen, versioned evaluation set with independently reviewed gold evidence for English, Japanese, and Bengali.
- Report Recall@k, MRR/nDCG, citation/evidence precision, answer faithfulness, abstention on no-evidence queries, and p50/p95 latency.
- Segment by query language, source language, mixed-language queries, document type, and lexical/semantic fallback.
- Do not claim improved quality from synthetic examples alone; require a reproducible baseline and paired comparison before enabling a new retriever by default.

## LiveKit voice acceptance

- Do not create or deploy an agent into the CLI-visible `aqlyra-rag-ai-jooglmob.livekit.cloud` project while production backend logs target `aqlyra-whhfocpe.livekit.cloud`.
- First obtain access to the exact production LiveKit project (or have its owner invite the operator account with the required write permission).
- Deploy the worker and API from compatible revisions, then verify dispatch, join, bidirectional audio, transcript persistence, document scope, auth-epoch revocation, disconnect/reconnect, and cost/quota behavior.
- Keep production voice unavailable until the full end-to-end test passes.

## Rollback and release checklist

- Confirm database backup and restore point before the refresh-session migration.
- Apply additive migration on staging; verify old browser sessions upgrade and concurrent refresh is idempotent.
- Deploy API and BFF as one coordinated release; verify refresh rotation, logout, password reset, replay detection, and cold-start recovery.
- Deploy API and LiveKit worker together for auth-epoch metadata changes.
- Verify durable storage before enabling document writes.
- Verify release-branch ruleset and required checks before merging.
- Keep `main`, production Render, production Neon, and production secrets unchanged until explicit release approval.
