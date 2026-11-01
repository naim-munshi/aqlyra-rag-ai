# Aqlyra Voice: minimal deployment plan

## Single production architecture

Existing **Vercel** Next.js frontend -> **Render** FastAPI (the only chat/RAG brain) -> existing **Neon PostgreSQL/pgvector** and **Redis**. The dedicated LiveKit voice worker calls the same `execute_chat_turn`, auth and conversation persistence. Do not create a second frontend, API, database or AI brain just for voice.

The separate Render semantic-embedding worker exists for 512-MiB memory constraints; SearXNG is experimental while Tavily remains the accepted production Web Search provider. Preserve both unless separately reviewed.

## Keep one voice deployment path

**Preferred existing path: Railway staging `aqlyra-voice-worker`.**

- Repository: `naim-munshi/aqlyra-rag-ai`, branch `fix/voice-call-reliability-20261101` (follow branch, no stale SHA pin).
- Root/build context: `/backend`; Dockerfile: `Dockerfile.voice`; no public HTTP port; one continuously running worker.
- Docker startup: `python -m app.voice.preflight && exec python -m app.voice.worker start` (the existing image command). It validates configuration before the RTC worker starts.
- Match the **actual live Render** API configuration for `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` and any embedding credentials. Do not substitute a different vector model with the same dimensions.
- LiveKit/Groq credentials are staged in Railway; verify their real values without revealing them. GitHub Actions Secrets do not read Railway variables automatically. Keep `VOICE_AGENT_READY=false` in the API until audio E2E passes.
- **Do not accept the mixed Railway staging patch.** It includes unprovisioned duplicates of the existing Vercel frontend, Render backend, Neon PostgreSQL and storage volumes. These should be discarded **in the Railway dashboard** (connector does not currently support removing staged-only resources). Preserve the standalone voice worker's staged settings.
- Railway free resource limits/costs may still prevent a separate worker. If it cannot be hosted, LiveKit Cloud remains an optional **manual** alternative, not a second parallel GitHub deployment workflow. Avoid writing or distributing credentials.

## Readiness / release gates

1. Source and compatibility: current worker branch must match live Render database schema, auth contracts, embeddings, and RAG settings. No migrations or data changes are approved for this cleanup.
2. Confirm Railway deploy succeeds, agent registers with the same LiveKit project and `VOICE_AGENT_NAME=aqlyra-voice`, and provider quotas are adequate.
3. Test actual authenticated microphone -> STT -> Aqlyra answer -> audible TTS on a phone (Bangla, Japanese, English); verify two-account access isolation, conversation persistence, mute, hangup and revoked user handling.
4. Only then enable API `VOICE_AGENT_READY`; confirm rollback. Browser Web Speech fallback is not evidence of LiveKit acceptance.

**Status:** Code/CI may pass while RTC worker deployment and live audio remain BLOCKED. Keep production, main branch and existing user data unchanged until the gates pass.
