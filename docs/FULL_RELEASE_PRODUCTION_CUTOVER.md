# Aqlyra — full-release production cutover control (2026-10-28)

This document supersedes the **core-only** deployment snapshot in
`docs/PRODUCTION_LIVE_FIRST_RUNBOOK.md`. Production still uses an
access-controlled Vercel origin. This is NOT public launch authorization.

## Verified reference state (2026-10-28, refreshed after Core bootstrap)

| Surface | Evidence and release state |
|---|---|
| PR #37 | DRAFT / unmerged; protected `main` unchanged. Review and approval still required. |
| Full Release branch | `release/full-with-study-abroad-20261028`, candidate `5c6d875a14c54e52d34c87abe94fce36ba00493b` passed 7/7 GitHub CI, including real PG16/PG18 Study Abroad schema catalog tests and synthetic S3 HTTP application restart. Later recovery script/runbook commits require their own exact-head CI before cutover. PR #37 remains Draft. |
| Core branch | `release/core-without-study-abroad-20261027`, cleanup commit `dc3920fb1428e143b8c393fd25941f7206c35b4c` exact-head CI 7/7 PASS. Temporary DB hostname diagnostic removed. |
| Render backend | Existing `srv-dbgjt0ei0phs73akd8j0` core-only branch, auto-deploy OFF, exact cleanup SHA LIVE at `dep-dbgo7nh42hec73dkfc4g`. One-time Core migration completed and `DATABASE_MIGRATION_MODE` restored to `manual` (no startup auto migration). |
| Read-only external probe | GitHub run `40624724953`, job `122644969614`: HTTP 200 for `/api/v1/health` and strict `/api/v1/readiness`. Study Abroad routes remain 404 until Full Release backend. This proves Core dependency readiness, **not** logged-in RAG E2E. |
| Neon | **2026-10-28 owner-approved Full migration APPLIED in one atomic transaction** to default `production` branch `br-morning-water-a1lgl3s4`, project `rough-river-66110449`, DB `neondb`, role `neondb_owner`. Independent postflight: Alembic `d4ec2f9b7860` (one row), **20** public tables, all four Study Abroad tables, 5 correct cascade FKs, 3 ordered BTREE indexes, 4 PKs, pgvector present; users=0, documents=0. This is schema acceptance only, not Full backend E2E. |
| Recovery | **Pre-migration Core** owner-private Neon pg_dump/SHA-256 and isolated PG18 Docker restore: PASS (`b5e4a019dc72`). Backup bytes stayed on the owner's Mac; pre-Core snapshot `snap-restless-mouse-a144fpzy` and protective pre-Full Core branch `br-damp-credit-a1mksvnz` are retained. A **fresh post-migration Full schema off-host backup plus isolated restore** is a new mandatory pre-Full backend cutover gate (NOT YET RUN). Do not reset or downgrade production by dropping the new Study Abroad tables. |
| Vercel | Production READY, protected via Vercel Authentication on all deployments. Keep private through acceptance. |
| Object storage | Neon private bucket `private-documents` exists. Generated artifacts currently use local `UPLOAD_DIR/artifact-workspace` and are NOT verified durable across Render Free restarts. Do not assume file history or document uploads survive redeploy without validated remote storage. |
| LiveKit | `aqlyra-voice` worker has no independently verified running deployment or real microphone/STT/RAG/TTS acceptance. |

**Never disclose, print, commit, or paste secret values.** Render key values
are deliberately inaccessible to this runbook; check via service startup
errors and provider dashboard, not secret decryption.

## Cutover steps, in required order

1. **Reverify provider configuration without reading secret values.** Render now starts and reaches PostgreSQL; earlier missing-key logs are historical and should not be treated as current blockers. Require real private Groq/Hugging Face access, Redis TLS and fail-closed rate limiting, Google OAuth, Resend sender verification, quotas, and isolated full E2E acceptance. Existing non-secret examples: `LLM_PROVIDER=groq`, `EMBEDDING_PROVIDER=huggingface`, `VOICE_AGENT_NAME=aqlyra-voice`, `CORS_ORIGINS=https://aqlyra-navy.vercel.app`, and `RAG_GROUNDING_VERIFIER_ENABLED=true`. Do not substitute placeholders or disable security checks to make readiness green.
2. **Preserve the now-migrated Full database and previous Core recovery branch.** Neon production currently has `d4ec2f9b7860`; never rerun the old Core bootstrap or `d4ec2f9b7860` upgrade. Preserve the no-compute pre-Full Core recovery branch and original snapshot. Before Full backend cutover, obtain a fresh owner-private **Full-head** pg_dump and network-isolated restore with the reviewed recovery gate's `--expected-phase full` mode. Verify the live Full schema before and after. Prior Core archive is not the new Full-head backup.
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
   A **new post-Full-migration** owner-private backup and isolated restore is REQUIRED before Full Render deployment; use `--expected-phase full` against the current production revision `d4ec2f9b7860`. The previous Core archive remains an earlier point-in-time recovery artifact only.
3. **Full migration already APPLIED; do not repeat.** The owner approved and an atomic production SQL transaction added exactly four Study Abroad tables and three indexes with five cascade FKs, then advanced Alembic from `b5e4a019dc72` to `d4ec2f9b7860`. Independent Neon postflight verified the result. Keep Render `DATABASE_MIGRATION_MODE=manual` and preserve old recovery data. Schema success does **not** authorize the pending Full Render deployment or public launch.
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

## Remaining post-migration recovery and release gates (new schema writes require separate approval)

- **Core bootstrap is complete.** Never reset or rerun the initial chain. Confirm the current revision and counts via read-only SQL immediately before cutover.
- **Existing protection:** keep `snap-restless-mouse-a144fpzy` (pre-Core, empty) and the no-compute Core branch `br-damp-credit-a1mksvnz`; do not delete either. A second snapshot may be unavailable on Neon Free. Neither is verified cross-provider disaster recovery.
- **Recovery rehearsal:** real operator-owned off-host backup and separate isolated Docker restore were observed PASS on 2026-10-28. This is a Core schema restore only, not a Full migration or recovery of non-database upload files. Do not reset production; actual restore/reset or new schema migration requires explicit owner approval. Preserve private document storage separately.
- **Full migration:** `b5e4a019dc72` -> `d4ec2f9b7860` applied 2026-10-28 on the approved Neon production branch; read-only postflight PASS. Do not run it again. Before Render Full cutover obtain a new private off-host Full database backup and isolated restore; preserve the earlier Core recovery branch without resetting production.
- **Application durability:** artifact generation uses local Render storage; create/enable a verified private, durable backend before marking AI document history production ready. Treat uploaded local documents with the same caution.
- **Release acceptance:** after approved migration and backend branch switch, require Full readiness HTTP 200, workflows 200, anonymous cases 401, authenticated cases/documents scoped to two separate test accounts, RAG citations, voice audio and restart-persistence verification.

## Free-tier limitations

Vercel Hobby is not suitable for a commercial public launch, Render Free
sleeps when inactive and has ephemeral disk, and LiveKit Build quotas are
limited. A protected owner-controlled test can stay on free-tier service
allowances. Do not authorize paid upgrades automatically.

**Current honest verdict:** Production Full Study Abroad **database migration PASS**, Core-only Render deployment remains LIVE with auto-deploy OFF. Post-migration Core HTTP readiness is not yet independently verified. Full backend branch switch, authenticated Study Abroad endpoints, production voice, original document/artifact durability and real two-user E2E remain NOT ACCEPTED. The site is not approved for public launch.
