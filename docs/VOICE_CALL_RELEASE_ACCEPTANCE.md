# Aqlyra Voice Call — release acceptance (2026-11-01)

**Status: code fixes are on a review branch; real production voice is not accepted.**

## Verified gap

- Vercel production is on frontend commit `9420c4c6` (release/unified-core-frontend-rag-20261031).
- Render Core API is on commit `b21c7c0`. In the connected Render workspace,
  the API, semantic worker and SearXNG are present, but there is **no separate
  running LiveKit voice agent worker**. The existing `backend/Dockerfile.voice`
  and Python worker code are not the same as a running deployment.
- `VOICE_AGENT_READY` defaults to false. Its authenticated status endpoint
  validates configuration/flag, not actual agent registration or audible output.

## Fixes implemented on the review branch

- Browser voice starts speech recognition in the original user tap,
  while conversation creation happens asynchronously.
- Muting while the AI request is in flight suppresses late audio playback
  and prevents overlapping turns after an immediate unmute.
- Intentional TTS cancellation on mute/hangup no longer reports a false error.
- Browser audio must fire speech synthesis `onstart` before the UI claims
  the agent is speaking; absent start or stalled playback recovers with
  a visible error and resumes listening. Full response text remains in chat.
- On iPhone Safari when automatic browser speech is blocked, the call UI
  offers **Tap to hear reply**. Replaying the latest response starts directly
  from the user's button press and remains disabled when muted or hung up.
- Logged-out HTTP 401 on the voice status check cannot trigger an
  unauthenticated microphone prompt, even when browser speech is supported.
- Immediate microphone permission failure invalidates pending startup state.
- Browser speech uses the device/browser speech services. It is **not**
  LiveKit full-duplex voice, and mobile support is device dependent.

## Voice agent activation prerequisites (operator action)

1. Deploy the existing `backend/Dockerfile.voice` as a separate LiveKit
   agent worker on suitable infrastructure (e.g. a Render background worker
   or LiveKit Cloud agent deployment), using a reviewed exact source SHA.
   Its runtime entrypoint is `python -m app.voice.worker start`.
2. Privately configure the worker with same LiveKit project URL/API key/secret
   as backend, `SECRET_KEY`, an approved PostgreSQL `DATABASE_URL`, provider
   the LiveKit Inference STT/TTS models and speech capacity. The existing
   Aqlyra brain uses its selected LLM/embedding provider credentials; Groq
   is not required for LiveKit Inference speech.
   Provision required Redis and other app dependencies through private
   provider dashboards. Never paste or log secret values.
3. Confirm the worker registers exactly the same `VOICE_AGENT_NAME`
   (`aqlyra-voice` by default) used for backend explicit room dispatch.
   A syntactically valid URL and room token do **not** prove registration.
4. Complete an isolated two-account staging call, actual microphone
   STT -> AI -> TTS audible output, auth revocation, hangup and provider
   outage test. Record device, timestamp, source SHAs and sanitized evidence.
5. Only after independent acceptance explicitly enable production
   `VOICE_AGENT_READY=true`. If the worker fails, turn issuance OFF
   and keep text chat/browser fallback available where supported.
6. Verify memory and provider pricing before provisioning paid capacity.

Official worker deployment guidance: https://docs.livekit.io/deploy/custom/deployments/

## Acceptance matrix (none of these is claimed as live-pass)

| Check | Evidence still required |
| --- | --- |
| Worker registered and assigned to named room | **BLOCKED** — service absent |
| iPhone Safari and Android browser mic -> audible AI reply -> next turn | Device E2E |
| English, Japanese and Bangla speech quality | Human-reviewed real STT/TTS |
| Two independent accounts and cross-owner denials | Live API/voice E2E |
| Delayed reply while muted, cancel/hangup and audio unlock | Offline tests added; real device pending |
| Worker/provider outage, restart recovery, metrics and rollback | Provider-backed acceptance |

## Release boundary

Do not merge protected `main`, enable the production flag or deploy
unfinished changes until exact-head CI, required review, worker/provider
acceptance and the owner's release approval pass. Preserve existing user
accounts, files, conversation history and database schema. No live data
migration or service creation is implied by this document.

## Voice worker startup preflight (2026-11-01)

The existing `backend/Dockerfile.voice` now runs `python -m app.voice.preflight` before registering a LiveKit agent. It validates APP_ENV, SECRET_KEY, DATABASE_URL, REDIS_URL, LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, VOICE_AGENT_NAME, selected STT/session model providers and TTS model/voice. Provider credentials are required **only for selected providers** (Groq is optional); it validates production mode, transport syntax and minimum secret length, and logs **no secret values**. This is not proof that the external providers are reachable or have working quotas.

For an isolated new Railway voice worker, use repository `naim-munshi/aqlyra-rag-ai`, build context/root directory `backend`, Dockerfile `Dockerfile.voice`, default Docker CMD (no HTTP port/public URL), continuous worker and private production-like staging variables (stored only in the provider secret dashboard). Use a separate LiveKit project and disposable test database for staging. **Do not commit the existing Railway staging patch** (56 old unrelated service/database changes) just to start the voice worker. A separately deployed, reviewed worker with approved billing and secrets is required before `VOICE_AGENT_READY=true` on the actual API.


## Dedicated worker production role — 2026-11-01 startup blocker

The voice worker Docker image sets `AQLYRA_PROCESS_ROLE=voice_worker`.
This bypasses **only HTTP API-specific** Google OAuth, email delivery and
CORS requirements. `app.main` refuses the worker role, preventing a public
API server from inheriting these exemptions.

Common production security remains mandatory: strong `SECRET_KEY` and
PostgreSQL password, Redis, `RATE_LIMIT_ENABLED=true`,
`RAG_GROUNDING_VERIFIER_ENABLED=true`, real LLM/embedding providers,
verified email policy and `DEBUG=false`.

Configure in the worker provider's secret UI, never in Git:
`APP_ENV=production`, `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`,
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
`VOICE_AGENT_NAME` (same as API), `VOICE_STT_PROVIDER=livekit`,
`VOICE_STT_MODEL=deepgram/nova-3`, `VOICE_STT_LANGUAGE=multi`,
`VOICE_SESSION_LLM_PROVIDER=livekit`, `VOICE_SESSION_LLM_MODEL=openai/gpt-oss-120b`,
`VOICE_TTS_MODEL=cartesia/sonic-3`, `VOICE_TTS_VOICE`,
`RATE_LIMIT_ENABLED=true`, `RAG_GROUNDING_VERIFIER_ENABLED=true`,
`LLM_PROVIDER` plus its matching model/credential, and a non-deterministic
`EMBEDDING_PROVIDER` with its corresponding credential (for example
the Hugging Face `HF_TOKEN` or OpenAI `OPENAI_API_KEY`).

The startup preflight validates configuration only; it does not prove
LiveKit worker registration, quotas or real audio. The connected Railway
staging voice service still has zero deployments and missing provider
variables. Leave API-side `VOICE_AGENT_READY=false` until worker
registration and real speech E2E tests pass.


## Hybrid Voice: LiveKit Speech and the existing Aqlyra AI Brain (2026-11-02)

The speech path is LiveKit WebRTC -> LiveKit Inference Deepgram Nova-3
multilingual transcription -> AqlyraVoiceAgent.llm_node -> existing
execute_chat_turn() with RAG, citations, conversation scope and memory ->
LiveKit Inference Cartesia Sonic 3 speech. No new chat brain is introduced.

By default VOICE_STT_PROVIDER=livekit and VOICE_SESSION_LLM_PROVIDER=livekit.
The session model fulfils LiveKit AgentSession's interface; all actual
answers come from execute_chat_turn(). Direct Groq STT/session models are
optional opt-ins and then require GROQ_API_KEY. If the Aqlyra brain itself
uses LLM_PROVIDER=groq, it still needs the Groq key; use a configured
LLM_PROVIDER=openai with OPENAI_API_KEY to run without Groq entirely.

LiveKit Cloud quotas/billing and a running worker are still required.
Language recognition and speech must be tested by real Bengali, Japanese
and English speakers; service registration is not yet verified.
Never set VOICE_AGENT_READY=true before mobile RTC owner acceptance.
