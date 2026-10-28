# Aqlyra — full-release production cutover control (2026-10-28)

This document supersedes the **core-only** deployment snapshot in
`docs/PRODUCTION_LIVE_FIRST_RUNBOOK.md`. Production still uses an
access-controlled Vercel origin. This is NOT public launch authorization.

## Verified reference state (2026-10-28, refreshed after Core bootstrap)

| Surface | Evidence and release state |
|---|---|
| PR #37 | DRAFT / unmerged; protected `main` unchanged. Review and approval still required. |
| Full Release branch | `release/full-with-study-abroad-20261028`, commit `c7418fd759c67fe37a69040e91ec24b9eb3d7132` passed 7/7 CI (PG16/PG18, ARM64, frontend, security, synthetic restore). Later commit `77ceeee35a09e0972fac7341faf8ad41ce28687e` fixes a psycopg cursor query bug; reverify exact-head CI before a production cutover. |
| Core branch | `release/core-without-study-abroad-20261027`, cleanup commit `dc3920fb1428e143b8c393fd25941f7206c35b4c` exact-head CI 7/7 PASS. Temporary DB hostname diagnostic removed. |
| Render backend | Existing `srv-dbgjt0ei0phs73akd8j0` core-only branch, auto-deploy OFF, exact cleanup SHA LIVE at `dep-dbgo7nh42hec73dkfc4g`. One-time Core migration completed and `DATABASE_MIGRATION_MODE` restored to `manual` (no startup auto migration). |
| Read-only external probe | GitHub run `40624724953`, job `122644969614`: HTTP 200 for `/api/v1/health` and strict `/api/v1/readiness`. Study Abroad routes remain 404 until Full Release backend. This proves Core dependency readiness, **not** logged-in RAG E2E. |
| Neon | Connected `rough-river-66110449`, branch `br-morning-water-a1lgl3s4`, DB `neondb`, role `neondb_owner`. Independently read-only verified Core Alembic `b5e4a019dc72`, **16** application tables, pgvector installed, users=0, documents=0. Full Study Abroad revision `d4ec2f9b7860` NOT applied. |
| Recovery | **Owner-run real Neon private backup and SHA-256: PASS; isolated networkless Docker PG18 restore and revision `b5e4a019dc72`: PASS** (owner-supplied console evidence, 2026-10-28). Independent live read-only Neon postflight: same revision, pgvector present, no Study Abroad tables, zero users/documents. Full wrapper itself stopped before restore because Docker was initially off; the owner ran the restore separately, so do not claim the wrapper exited successfully. Original pre-Core snapshot `snap-restless-mouse-a144fpzy` and no-compute Core recovery branch `br-damp-credit-a1mksvnz` remain READY/preserved. The private backup bytes were not shared with GitHub or ChatGPT. |
| Vercel | Production READY, protected via Vercel Authentication on all deployments. Keep private through acceptance. |
| Object storage | Neon private bucket `private-documents` exists. Generated artifacts currently use local `UPLOAD_DIR/artifact-workspace` and are NOT verified durable across Render Free restarts. Do not assume file history or document uploads survive redeploy without validated remote storage. |
| LiveKit | `aqlyra-voice` worker has no independently verified running deployment or real microphone/STT/RAG/TTS acceptance. |

**Never disclose, print, commit, or paste secret values.** Render key values
are deliberately inaccessible to this runbook; check via service startup
errors and provider dashboard, not secret decryption.

## Cutover steps, in required order

1. **Reverify provider configuration without reading secret values.** Render now starts and reaches PostgreSQL; earlier missing-key logs are historical and should not be treated as current blockers. Require real private Groq/Hugging Face access, Redis TLS and fail-closed rate limiting, Google OAuth, Resend sender verification, quotas, and isolated full E2E acceptance. Existing non-secret examples: `LLM_PROVIDER=groq`, `EMBEDDING_PROVIDER=huggingface`, `VOICE_AGENT_NAME=aqlyra-voice`, `CORS_ORIGINS=https://aqlyra-navy.vercel.app`, and `RAG_GROUNDING_VERIFIER_ENABLED=true`. Do not substitute placeholders or disable security checks to make readiness green.
2. **Preserve the verified migrated Core database and recovery branch.** Neon is correctly connected; Core `b5e4a019dc72` is already applied. Before further migrations, confirm exact target, current data counts, the non-default Core recovery branch and a usable isolated restore procedure. Do not waste time repeating Core bootstrap or overwrite the existing snapshot. A Neon branch is not a substitute for independent off-host restore rehearsal.
   To run the *actual* private Neon off-host backup and isolated restore
   from an owner-authenticated Mac, follow
   `docs/NEON_FULL_RELEASE_SAFE_CUTOVER.md`, section 4A, with
   `scripts/ops/neon_full_release_recovery_gate.sh`. Its credentials
   stay in a 0600 local file. **2026-10-28 evidence:** owner-run live
   Neon backup creation, structural check and SHA256 succeeded, then the
   wrapper stopped because Docker Desktop was initially unavailable.
   After starting Docker, the owner ran the matching archive and manifest
   through `neon_restore_rehearsal.sh` and obtained
   `RESTORE_REHEARSAL=PASS`, restored revision `b5e4a019dc72`, and
   disposable-container cleanup PASS. Independent live Neon postflight
   confirmed the unchanged Core schema. Thus the constituent real backup
   and isolated restore acceptance passed; do not claim the all-in-one
   wrapper itself exited 0. Keep the private archive off-repository.
   If further schema changes occur, repeat backup/restore for the new state.
3. **Review the additive Full migration with a controlled recovery plan.** Revision `d4ec2f9b7860` depends on `b5e4a019dc72` and adds the four Study Abroad tables. Verify no drift or unexpected data changes and confirm both source and recovery. Only with explicit authorization execute the reviewed upgrade on the verified intended database. Keep Render migration mode `manual`; never enable startup auto-migrations for normal deploys. Afterward query `public.alembic_version` and table ownership, and verify Full readiness independently.
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

## Remaining database recovery and migration gates (require explicit owner approval for schema writes)

- **Core bootstrap is complete.** Never reset or rerun the initial chain. Confirm the current revision and counts via read-only SQL immediately before cutover.
- **Existing protection:** keep `snap-restless-mouse-a144fpzy` (pre-Core, empty) and the no-compute Core branch `br-damp-credit-a1mksvnz`; do not delete either. A second snapshot may be unavailable on Neon Free. Neither is verified cross-provider disaster recovery.
- **Recovery rehearsal:** real operator-owned off-host backup and separate isolated Docker restore were observed PASS on 2026-10-28. This is a Core schema restore only, not a Full migration or recovery of non-database upload files. Do not reset production; actual restore/reset or new schema migration requires explicit owner approval. Preserve private document storage separately.
- **Full migration:** only `b5e4a019dc72` -> `d4ec2f9b7860` remains, not the base-to-Core migration. Before any schema change, check exact DB/role/branch, reviewed Alembic diff, storage/backup and authorized maintenance window.
- **Application durability:** artifact generation uses local Render storage; create/enable a verified private, durable backend before marking AI document history production ready. Treat uploaded local documents with the same caution.
- **Release acceptance:** after approved migration and backend branch switch, require Full readiness HTTP 200, workflows 200, anonymous cases 401, authenticated cases/documents scoped to two separate test accounts, RAG citations, voice audio and restart-persistence verification.

## Free-tier limitations

Vercel Hobby is not suitable for a commercial public launch, Render Free
sleeps when inactive and has ephemeral disk, and LiveKit Build quotas are
limited. A protected owner-controlled test can stay on free-tier service
allowances. Do not authorize paid upgrades automatically.

**Current honest verdict:** Core migrated/schema/pgvector/Redis readiness PASS LIVE; Full Release migration, Study Abroad endpoints, voice worker, generated-file durability and real two-user production E2E remain BLOCKED. The site is not yet approved for public launch.
