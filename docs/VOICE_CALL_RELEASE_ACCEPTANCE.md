# Aqlyra Voice Call — single release acceptance checklist

**Production:** Browser Voice fallback is available. Railway's LiveKit worker registered successfully in **staging** (`ca759453-6d80-4e1d-b8d3-34a4d5710c02`, `SUCCESS`, one replica); this **does not prove** an authenticated end-to-end audio call from the production API. Keep production `VOICE_AGENT_READY=false` until actual audio, identity and rollback gates pass.

## Existing implementation (do not duplicate)

- Current frontend: Vercel `aqlyra`; backend and RAG brain: existing Render FastAPI; persistent state: existing Neon PostgreSQL/pgvector and Redis.
- LiveKit worker: `backend/Dockerfile.voice`, started using its preflight-and-exec CMD. It uses `app.voice.worker` and the **same** `execute_chat_turn` (history, selected documents, RAG, citations, memory, persistence).
- Speech: LiveKit Inference Deepgram Nova-3 STT -> existing Aqlyra chat brain -> Cartesia Sonic 3 TTS. The session adapter model is **not** a second answer-generating AI service.
- Browser fallback: audio permission starts from user gesture, cancelled or muted replies cannot speak afterward, long requests time out, iOS may need **Tap to hear reply**. Browser speech is not proof of LiveKit operation.

## Deployment boundary

Use the **existing Railway staging voice worker only** for the current trial. The duplicate Railway frontend, backend, database and volumes were discarded; the worker was separately deployed from commit `e7f7a4e`, and the environment has **zero pending changes**. Keep Vercel frontend, Render API, Neon database and existing Redis. Do not recreate duplicate infrastructure. The new voice-intelligence fixes are in a separate draft PR and are **not released** yet.

Voice worker configuration preflight and LiveKit registration passed, but secret equality with Render, provider quotas and production user-session authorization remain unverified. It must use **the actual live Render** database/Redis/auth/embedding configuration. Voice and production Core Git branches have diverged; verify DB schema and conversation API compatibility before connecting to production accounts.

Detailed, single-path setup: [VOICE_FREE_TIER_SETUP.md](VOICE_FREE_TIER_SETUP.md).

## Conversation quality release gate

- Exact self-introduction: "Tell me about you" describes **Aqlyra's capabilities**, not its founder. The founder is named only if explicitly asked.
- English, বাংলা and 日本語: microphone transcripts preserve the actual spoken language. Do not inject voice-language hints into the user's stored question.
- Stop speaking: "stop", "থামো", "止めて" should promptly interrupt **LiveKit** speech, not generate a reply. Browser Voice exposes a **Stop reply** button because iOS browser STT cannot reliably listen while synthesizing.
- Browser fallback selects matching installed OS voices when available and offers a recognition-language selector. If the OS has no native-language voice, accent quality remains device-dependent.
- LiveKit Sonic 3 supports Bangla and Japanese (unlike Sonic 3.5 for Bangla). Optional verified `VOICE_TTS_VOICE_BN`, `VOICE_TTS_VOICE_JA`, `VOICE_TTS_VOICE_HI` provider-specific voice IDs can improve accents; **do not invent IDs**, and an empty value preserves the existing voice.
- Test sustained conversation, silence (no self-echo turns), interruption during long AI speech, repeated turns, code-switching, mute, hangup and restart on real devices.

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
