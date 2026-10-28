# Aqlyra — full-release production cutover control (2026-10-28)

This document supersedes the **core-only** deployment snapshot in
`docs/PRODUCTION_LIVE_FIRST_RUNBOOK.md`. Production still uses an
access-controlled Vercel origin. This is NOT public launch authorization.

## Verified reference state

| Surface | Verified state |
|---|---|
| GitHub candidate | PR #37, branch `release/full-with-study-abroad-20261028`, head `69c0a68b448cd75c8a0e1e31058e9e2ee5bc75a1` |
| Exact-head CI | 7/7 successful (including PG16/18, native ARM64 real E2E, frontend and Docker) |
| Vercel | Production READY from above exact head, deployment `dpl_5H1qFcDqaxZEfvXvXGTMwqjdafLd`, alias `https://aqlyra-navy.vercel.app`; Vercel Authentication enabled for **all** deployments |
| Render | Existing `aqlyra-api-free-launch`, ID `srv-dbgjt0ei0phs73akd8j0`, **core-only** branch and auto deploy off; latest check `dep-dbglnk49v7es73aqbth0` FAILED at backend Settings validation |
| Render secret progress | Previous deployments failed on absent `SECRET_KEY` and `DATABASE_URL`; a later deployment failed on `HF_TOKEN`; next deploy at 02:20 UTC progressed to **`GROQ_API_KEY` required**. The earlier errors no longer appeared in that latest startup attempt; this does NOT prove remote DB/Redis connections |
| LiveKit | Screenshot of owner project `aqlyra-rag-ai` showed **zero deployed agents**; WebRTC room may connect without AI replying |
| Neon | Owner's isolated Free `aqlyra-staging` (PG18); connected Neon management tool rejects project ID because of incompatible connection scope. No real migration or off-host recovery test verified |
| Review | PR #37 is draft; zero approving reviews; `main` not merged |

**Never disclose, print, commit, or paste secret values.** Render key values
are deliberately inaccessible to this runbook; check via service startup
errors and provider dashboard, not secret decryption.

## Cutover steps, in required order

1. **Make Render start, without weak bypasses.** Owner enters
   `GROQ_API_KEY` as a nonempty active secret in the **correct** Render
   service. `HF_TOKEN` was previously accepted by settings validation;
   do not reassign it or other secrets to placeholders. Existing safe
   non-secret Render values already set:
   `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-20b`,
   `EMBEDDING_PROVIDER=huggingface`,
   `EMBEDDING_MODEL=ibm-granite/granite-embedding-97m-multilingual-r2`,
   `VOICE_AGENT_NAME=aqlyra-voice`,
   `CORS_ORIGINS=https://aqlyra-navy.vercel.app`,
   `RAG_GROUNDING_VERIFIER_ENABLED=true`.
   **Service start is not acceptance.** Recheck required Redis TLS, Google
   OAuth client, Resend API key and verified sender and the actual Groq/HF
   inference quotas using redacted logs and private dashboards.
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

## Free-tier limitations

Vercel Hobby is not suitable for a commercial public launch, Render Free
sleeps when inactive and has ephemeral disk, and LiveKit Build quotas are
limited. A protected owner-controlled test can stay on free-tier service
allowances. Do not authorize paid upgrades automatically.

**Current honest verdict:** Source/tests PASS, protected frontend READY;
public backend + LiveKit + Study Abroad real-data launch BLOCKED pending
external provider setup, reviewed migration, worker deployment and E2E QA.
