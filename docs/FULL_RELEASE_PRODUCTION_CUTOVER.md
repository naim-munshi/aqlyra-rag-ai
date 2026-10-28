# Aqlyra — full-release production cutover control (2026-10-28)

This document supersedes the **core-only** deployment snapshot in
`docs/PRODUCTION_LIVE_FIRST_RUNBOOK.md`. Production still uses an
access-controlled Vercel origin. This is NOT public launch authorization.

## Verified reference state (updated 2026-10-28 05:05 UTC)

| Surface | Verified state |
|---|---|
| GitHub candidate | PR #37, draft, unmerged; Full branch `release/full-with-study-abroad-20261028` at `2c5cb54c6f71ac7b8ff7b5122fbffe05caf1cef8` (verify the head again before release) |
| Exact-head CI | Full Release 7/7 PASS at the above head. Core branch `cf3835402d939df28726abb05dafe0d7c26d6b7b` 7/7 PASS. These are predeploy/synthetic gates, not live RAG acceptance. |
| Vercel | Production READY, `dpl_5H1qFcDqaxZEfvXvXGTMwqjdafLd`, `https://aqlyra-navy.vercel.app`; Vercel Authentication enabled for all deployments. |
| Render | `aqlyra-api-free-launch` remains core-only with auto-deploy disabled; core diagnostic SHA `cf3835402d939df28726abb05dafe0d7c26d6b7b` verified LIVE at 05:02:39 UTC (`dep-dbgo383bc2fs73b87vng`), with additional same-SHA redeploys queued. Do not trigger more until queue stabilizes. |
| Public backend probe | Read-only GitHub job `122642307809` at 05:03:50 UTC: /health 200, /readiness 503, Study Abroad workflows 404, anonymous cases 404. FAIL-CLOSED schema readiness is working. |
| Render failure stage | Safe log: `stage=schema_revision error_type=ProgrammingError approved_neon_target=true`. Boolean proves approved Neon *hostname* match only, not exact database contents or restore coverage. Do not expose the DSN. |
| Neon | Management connector works for `rough-river-66110449` (Singapore, PG18). Exactly one branch `br-morning-water-a1lgl3s4` (`production`) and one user database `neondb`; application tables, Alembic revision and pgvector absent. |
| Recovery | Snapshot `snap-restless-mouse-a144fpzy` exists but captures the EMPTY schema; isolated restore rehearsal is NOT_RUN. It is not a verified backup of any other data source. |
| LiveKit | Previous owner evidence showed no `aqlyra-voice` agent deployment. Running status / real microphone/STT/RAG/TTS acceptance not yet independently verified. |
| Review | PR #37 remains draft, no approval and no `main` merge. No public launch authorization. |

**Never disclose, print, commit, or paste secret values.** Render key values
are deliberately inaccessible to this runbook; check via service startup
errors and provider dashboard, not secret decryption.

## Cutover steps, in required order

1. **Reverify provider configuration without reading secret values.** Render now starts and reaches PostgreSQL; earlier missing-key logs are historical and should not be treated as current blockers. Require real private Groq/Hugging Face access, Redis TLS and fail-closed rate limiting, Google OAuth, Resend sender verification, quotas, and isolated full E2E acceptance. Existing non-secret examples: `LLM_PROVIDER=groq`, `EMBEDDING_PROVIDER=huggingface`, `VOICE_AGENT_NAME=aqlyra-voice`, `CORS_ORIGINS=https://aqlyra-navy.vercel.app`, and `RAG_GROUNDING_VERIFIER_ENABLED=true`. Do not substitute placeholders or disable security checks to make readiness green.
2. **Check the isolated Neon database and backups.** Verify the correct
   PG18 project and DB, not an unrelated production account. Reconnect
   the mis-scoped Neon plugin if necessary. Before migrations, take a
   recoverable snapshot/backup and rehearse a restore on an isolated
   test database/branch. Never assume a Render Free local file is durable.
3. **Review migrations in the full release**, not the old core:
   full-release Alembic head `d4ec2f9b7860` adds Study Abroad after
   `b5e4a019dc72` (cloud document tombstones). Verify there is exactly
   one head and no unexpected changes before manually applying
   `alembic upgrade head` in an explicitly selected, backed-up isolated
   Neon database with an owner-controlled environment. Do **not** run
   automatic migrations at Render startup.
4. **Switch Render to the full-release branch** using Render dashboard
   → service Settings → Build & Deploy → Branch →
   `release/full-with-study-abroad-20261028`; leave auto-deploy
   disabled until approval. This action is **not supported by the current
   connected Render tool**, so the authenticated owner must do it.
   Trigger one manual deploy, verify the exact Git SHA in Render, and
   check:
   - `GET https://aqlyra-api-free-launch.onrender.com/api/v1/health`
     must return healthy HTTP 200;
   - `GET https://aqlyra-api-free-launch.onrender.com/api/v1/readiness`
     must return ready HTTP 200 only after DB/Redis/storage validation;
   - all Study Abroad private case/document endpoints require the
     correct logged-in user and enforce owner isolation;
   - document parsing + semantic retrieval returns real citations and
     never crosses tenants. Synthetic CI does not replace provider E2E.
5. **Deploy voice separately** to owner's LiveKit Cloud
   `aqlyra-rag-ai` as registered agent name `aqlyra-voice` (the
   screenshot had zero agents). Follow
   `docs/LIVEKIT_VOICE_CLOUD_RUNBOOK.md`; the GitHub bundle contains
   the real RAG-backed agent and no secrets. Set matching `LIVEKIT_URL`,
   `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` privately on Render.
   Test Bangla, Japanese and English microphone/STT/RAG/TTS plus agent
   disconnect, missing agent, cost/quota, mute, hangup and retry.
6. **Privacy/security release gates:** verify two-account auth and
   private Study Abroad document isolation; Google OAuth callback;
   verified Resend email and anti-abuse; rate-limiting against real
   Upstash; no exposed admin/metrics, public storage or unsafe signed
   uploads; consent-aware memory. Keep
   `NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED=false` and
   `CLOUD_UPLOAD_PUBLIC_ENABLED=false` unless externally validated.
   Keep Vercel Authentication on. Complete independent PR review and
   documented acceptance; **do not merge protected `main` or open
   public registrations on CI status alone**.

## Greenfield Neon initial-schema decision gate (NOT YET AUTHORIZED)

- **Identification:** approved Neon hostname match is observed, but explicitly verify database name, effective role and branch against the connected Neon project before any schema-changing action. Do not infer this from the prior HTTP 200 readiness implementation.
- **Data safety:** independent SQL currently shows zero application tables and no pgvector. This does **not** prove data in any other PostgreSQL instance or private object store were backed up. Check the intended application data retention/recovery scope first.
- **Recovery:** the existing empty-schema Neon snapshot is a useful rollback checkpoint, but a snapshot ID alone is not proof of successful restoration. Document and validate the isolated recovery process, with no destructive production restore; any real restore requires owner approval.
- **Migration chain:** initial users revision `b7369290f410` -> Core `b5e4a019dc72` -> Full `d4ec2f9b7860`, single linear sequence. The final migration adds private Study Abroad tables referencing existing users/documents. PostgreSQL 18/pgvector must be provisioned by reviewed migration steps, and schema checked afterward.
- **Execution:** prohibit Render startup auto-migrations, wrong-target DDL and downgrades. Do not begin until the exact identity/recovery gates above and explicit schema-change authorization are satisfied. After approval, validate Full revision, table ownership/isolation, Redis/storage readiness and live endpoint contracts.

## Free-tier limitations

Vercel Hobby is not suitable for a commercial public launch, Render Free
sleeps when inactive and has ephemeral disk, and LiveKit Build quotas are
limited. A protected owner-controlled test can stay on free-tier service
allowances. Do not authorize paid upgrades automatically.

**Current honest verdict:** Source/tests PASS, protected frontend READY, Core liveness PASS, strict database schema readiness BLOCKED; Full Release, LiveKit and Study Abroad real-data launch BLOCKED pending reviewed greenfield schema/recovery, authenticated worker deployment, actual provider access and two-user E2E QA.
