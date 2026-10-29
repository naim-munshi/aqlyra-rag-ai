# Aqlyra Voice Call — production review and release gate (2026-10-29)

## Scope / phase
- Core branch: `release/core-without-study-abroad-20261027` (despite its historical name, the owner-requested Study Abroad API is now live).
- Full frontend branch: `release/full-with-study-abroad-20261028` remains unmerged to protected `main`.
- Public Vercel site remains deployment-protected. RAG schema/migrations, Study Abroad, data ownership and upload policy are unchanged by this voice patch.
- Real-time voice is **not ready for public use** without a separately verified LiveKit worker and real provider acceptance. Offline tests are not evidence of an audio round trip.

## Verified root cause
Render's authenticated `POST /voice/session` returned HTTP 503 in production. The existing server checks `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` and `VOICE_AGENT_NAME`; no healthy running named LiveKit voice worker was independently verified. The old client hid errors after the request failed, making calls appear to do nothing. Do not place these secrets in public variables, GitHub or chat.

## New fail-closed behaviour
- Backend `GET /api/v1/voice/status` requires an authenticated, verified user and returns only `available` and safe `detail`; it never reveals secret names or values. Proxied by `GET /api/voice/status` with private no-store cache.
- Default `VOICE_AGENT_READY=false` blocks all room tokens. Operators must set it `true` **only after** the provider, worker and acceptance checks below pass; the flag itself does not test the worker.
- Missing configuration continues to return 503; no room token is issued. Validate owner documents before creating a persisted conversation.
- Frontend refuses a call without a ready response, exposes error messages in the composer, asks for microphone access on direct tap for Safari, allows an explicit Enable sound action when audio autoplay is blocked, ends abandoned calls after the agent join timeout and keeps the voice sheet within a phone viewport.
- The existing RAG-backed worker and account-scoped conversation context are retained.

## Prerequisites requiring private owner action
1. Set up a LiveKit Cloud project (verify cost/quota) and safely deploy **one** healthy named `aqlyra-voice` worker from the audited bundle `scripts/ops/livekit_voice_bundle.sh`. Use `lk agent status` and `lk agent logs`; no agent is deployed by these source-code changes.
2. Supply the real LiveKit connection values to **Render private environment**: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. Never put any in frontend `NEXT_PUBLIC_*`.
3. The agent needs its own *private* cloud-accessible approved Neon/Postgres/Redis, LLM and Groq STT credentials, TTS service/LiveKit inference capacity, and RAG/auth configuration; do not assume the Render environment is inherited automatically. Gmail API is an approved sender option in the offline secrets preflight, but owner consent is still required. Do not paste credentials into chats or logs.
4. Keep `VOICE_AGENT_READY=false` on Render until a test worker can reliably join and complete a secure real two-way STT→RAG→TTS call. Switch to true only as the controlled acceptance cutover. This feature flag does not provision the worker.

## Acceptance checklist (no user audio or secrets in logs)
- An authenticated `/voice/status` call returns `available=false` before cutover; anonymous requests return 401; no JWT issued by a missing provider.
- On explicit cutover, an authenticated non-admin user can connect to their own LiveKit room and the named agent joins within 20 seconds; no raw voice data is logged; failure automatically tears down the call.
- On iPhone Safari, microphone permission and speaker audio work following clear user taps. Also test denied microphone, silent audio, mute/unmute, end/rejoin, and agent outage.
- English/Japanese/Bangla speech uses the configured language/STT/TTS and the existing Chat/RAG engine. Knowledge-mode retrieval cites only documents owned by the same user; cross-user conversation/document access remains denied.
- Validate provider quotas, concurrent calls, token TTL, usage alerts, production backup/restore and private file durability before public availability.

**Last verified state:** frontend/backend changes are source/CI work; no LiveKit Cloud deployment or real voice round-trip proof. Keep voice disabled and communicate why; do not label it working until acceptance passes.


## Additional security and multilingual findings (2026-10-29)
- **Revocation boundary:** Source-level gap fixed on the proposed feature branch:
  a previously issued short-lived LiveKit job could outlive account deletion,
  email verification revocation, conversation removal or document removal.
  A centralized database-backed validator now checks all three scopes before
  provider setup, before private RAG generation, and again before transcript
  persistence. This is a code/test fix, not a claim that a production worker
  has been deployed.
- **Transport:** a configured LiveKit URI that is plaintext or points to a
  private/loopback host must never receive production room JWTs. The backend
  now restricts production transport to a safe public `wss://` endpoint;
  local `ws://` remains available for development only.
- **Bangla voice:** The default `cartesia/sonic-3.5` was an incompatible
  choice for the requested Bengali/Bangla (`bn`) voice path. LiveKit's
  current [Cartesia TTS model list](https://docs.livekit.io/agents/models/tts/cartesia/)
  lists `bn` for `cartesia/sonic-3` but not Sonic 3.5. The default has
  been changed to `cartesia/sonic-3`; EN/JA/BN audio is still **unverified**.
  Operators overriding `VOICE_TTS_MODEL` must check model-language coverage.
- **CI:** Run backend PostgreSQL 16/18 regression, frontend voice checks,
  security scanning and container acceptance before promoting these changes.
  A voice integration **cannot** PASS solely because static checks PASS.
