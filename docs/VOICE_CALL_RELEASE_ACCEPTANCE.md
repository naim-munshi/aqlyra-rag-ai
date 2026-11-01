# Aqlyra Voice Call — single release acceptance checklist

**Production:** Browser speech fallback exists; **real LiveKit WebRTC voice is not yet accepted**. The dedicated agent worker has no successful deployment or verified audio call. Keep `VOICE_AGENT_READY=false`.

## Existing implementation (do not duplicate)

- Current frontend: Vercel `aqlyra`; backend and RAG brain: existing Render FastAPI; persistent state: existing Neon PostgreSQL/pgvector and Redis.
- LiveKit worker: `backend/Dockerfile.voice`, started using its preflight-and-exec CMD. It uses `app.voice.worker` and the **same** `execute_chat_turn` (history, selected documents, RAG, citations, memory, persistence).
- Speech: LiveKit Inference Deepgram Nova-3 STT -> existing Aqlyra chat brain -> Cartesia Sonic 3 TTS. The session adapter model is **not** a second answer-generating AI service.
- Browser fallback: audio permission starts from user gesture, cancelled or muted replies cannot speak afterward, long requests time out, iOS may need **Tap to hear reply**. Browser speech is not proof of LiveKit operation.

## Deployment boundary

Use the **existing Railway staging voice worker only** for the current trial. Do not create another frontend/backend/database or accept the shared Railway staging patch to release voice. Existing Railway staging has **91 unapplied configuration changes** across a voice worker and redundant frontend/backend/PostgreSQL/volume resources; none of these staged resources has been deployed. The connected Railway tool cannot discard staged-only resources. Remove unrelated staged resources in the Railway dashboard before any isolated deploy.

Voice worker variable names appear staged, but secret values, provider quotas and network reachability remain unverified. It must use **the actual live Render** database/Redis/auth/embedding configuration. Voice and production Core Git branches have diverged, so independently verify DB schema and conversation API compatibility before connecting to production accounts.

Detailed, single-path setup: [VOICE_FREE_TIER_SETUP.md](VOICE_FREE_TIER_SETUP.md).

## Required acceptance (not yet verified)

| Gate | Required evidence |
| --- | --- |
| Source and CI | Exact-head PostgreSQL 16/18, frontend, security, ARM64, dependency and Docker checks pass |
| Dedicated runtime | Independent worker deployment succeeds, worker registers exactly `aqlyra-voice`, sanitized logs show healthy room dispatch |
| Identity/security | Authenticated users can start a call; a second account cannot read conversations/documents; revoked users and foreign IDs are denied |
| Real audio | iPhone/Android microphone -> Bangla/Japanese/English STT -> RAG answer -> audible TTS; consecutive turns, mute/hangup, reconnect, fallbacks |
| Reliability/cost | Rate limits, provider outages, resource/billing quotas, restart and rollback verified |

Only after these checks should the owner approve enabling `VOICE_AGENT_READY=true` on the existing API; it must be reversible. Passing unit tests or a configured LiveKit URL is **not** proof of an audible call.

**Do not** merge protected `main`, migrate/reset production data, change authentication keys or deploy duplicate infrastructure as part of voice cleanup.
