# Aqlyra Voice Call — single release acceptance checklist

**Production:** LiveKit worker is registered and Online on Railway. Render has a secure Voice API and `VOICE_AGENT_READY=true`, **but its startup diagnostics on 2026-11-02 identified missing `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`**. Thus the authenticated real-time session cannot yet be created. The official Voice UI must show a clear unavailable error rather than silently substituting Browser Voice. Never claim an audible E2E call until the existing matching LiveKit credentials are provisioned on Render and a real authenticated mobile call passes.

## Existing implementation (do not duplicate)

- Current frontend: Vercel `aqlyra`; backend and RAG brain: existing Render FastAPI; persistent state: existing Neon PostgreSQL/pgvector and Redis.
- LiveKit worker: `backend/Dockerfile.voice`, started using its preflight-and-exec CMD. It uses `app.voice.worker` and the **same** `execute_chat_turn` (history, selected documents, RAG, citations, memory, persistence).
- Speech: LiveKit Inference Deepgram Nova-3 STT -> existing Aqlyra chat brain -> Cartesia Sonic 3 TTS. The session adapter model is **not** a second answer-generating AI service.
- Real-time-only voice: microphone starts on direct user gesture, session requests are origin/auth checked, failed agent joins show explicit errors, abort/cleanup releases microphone on iOS. Do not silently fall back to Browser Voice.

## Deployment boundary

Use the **existing Railway staging voice worker only** for the current trial. The duplicate Railway frontend, backend, database and volumes were discarded; the worker was separately deployed from commit `e7f7a4e`, and the environment has **zero pending changes**. Keep Vercel frontend, Render API, Neon database and existing Redis. Do not recreate duplicate infrastructure. The new voice-intelligence fixes are in a separate draft PR and are **not released** yet.

Voice worker configuration preflight and LiveKit registration passed, but secret equality with Render, provider quotas and production user-session authorization remain unverified. It must use **the actual live Render** database/Redis/auth/embedding configuration. Voice and production Core Git branches have diverged; verify DB schema and conversation API compatibility before connecting to production accounts.

Detailed, single-path setup: [VOICE_FREE_TIER_SETUP.md](VOICE_FREE_TIER_SETUP.md).

## Conversation quality release gate

- Exact self-introduction: "Tell me about you" describes **Aqlyra's capabilities**, not its founder. The founder is named only if explicitly asked.
- English, বাংলা and 日本語: microphone transcripts preserve the actual spoken language. Do not inject voice-language hints into the user's stored question.
- Stop speaking: "stop", "থামো", "止めて" must interrupt **LiveKit** audio hands-free, not create a chat turn. Browser Voice stop buttons are not a replacement for natural full-duplex barge-in.
- Users must not manually choose the recognition language. LiveKit Nova-3 automatically detects language and the existing TTS router switches by final AI reply language.
- LiveKit Nova-3 `multi` can optionally bias recognition toward Bengali/Japanese/English/Hindi using `VOICE_STT_LANGUAGE_HINTS=bn,ja,en,hi`; this is not a language lock. The final response script (including genuine English answers to Bengali questions) selects the TTS language. Romanized Bengali with multiple Banglish markers retains Bengali routing.
- Accurate *native accents* still require provider-verified regional voice profiles and listening tests; correct language selection alone cannot guarantee natural speech.
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

`VOICE_AGENT_READY=true` has already been applied in a controlled Render release, but the startup diagnostics show the two LiveKit credential values absent. Provision those in the existing Render service and confirm correct account/project matching before calling this production-ready. Passing unit tests or a configured LiveKit URL is **not** proof of an audible call.

**Do not** merge protected `main`, migrate/reset production data, change authentication keys or deploy duplicate infrastructure as part of voice cleanup.
