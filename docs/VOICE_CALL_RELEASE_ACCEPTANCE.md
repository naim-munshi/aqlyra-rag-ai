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
   `GROQ_API_KEY` for STT/generation, and working TTS model/voice capacity.
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
