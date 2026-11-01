# Aqlyra LiveKit Voice — existing production recovery runbook

**Verified configuration audit: 2026-11-02 (JST).** The same Aqlyra service and data are retained; this is an operator runbook, **not** a real-audio acceptance certificate.

## Actual service map

| Service | Existing target | Most recently confirmed |
| --- | --- | --- |
| Frontend | [Vercel Aqlyra](https://aqlyra-ai.vercel.app) | Production deploy `dpl_CnwFJWRD2LRy7HcR1iso4Gha3hNr` READY, Voice UI requires real LiveKit, no browser-voice downgrade |
| API/chat brain | [Render aqlyra-api-free-launch](https://dashboard.render.com/web/srv-dbgjt0ei0phs73akd8j0) | Core release branch, deploy `dep-dbjr7is9v7es73au6ol0` LIVE, code `74f7a6d63e976aedfd6344afb08cdaeef9ad8cb0` |
| Realtime agent | Railway `Aqlyra-Staging` / `staging` / `aqlyra-voice-worker` | Deploy `396a246d-a8fb-406b-82ad-3aba3926f499` SUCCESS, `voice_worker_preflight=PASS`, `registered worker` |
| Data/memory | Existing Neon PostgreSQL, pgvector, Redis | **No new database**; worker uses the same authorized chat/RAG and owner-scoped data |
| Speech | Existing LiveKit Inference Deepgram Nova-3 and Cartesia Sonic 3 | Configured in current worker; no actual EN/BN/JA/HI end-to-end voice accepted yet |

**Precise P0 blocker:** Render startup at `2026-11-01T21:50:02Z` logged `voice_api_startup_ready=false` and `voice_api_startup_missing_keys=LIVEKIT_API_KEY,LIVEKIT_API_SECRET`. Railway lists both variable **names**, but connection redacts the values. **Never infer that keys match**. Render's `VOICE_AGENT_READY` flag alone is not proof of provider connectivity.

## Owner-only recovery: use the same LiveKit Cloud project

1. Open the **existing** [Render API service dashboard](https://dashboard.render.com/web/srv-dbgjt0ei0phs73akd8j0) and select **Environment**. Do not open a new Render account/service or rotate the database/auth key.
2. In the **existing LiveKit Cloud project** used by the Railway `aqlyra-voice-worker`, locate its authorized project API key/secret through the provider's normal secret-management workflow. Confirm the project corresponds to the worker's current `LIVEKIT_URL` and `VOICE_AGENT_NAME=aqlyra-voice`; do not assume keys from another LiveKit project will work.
3. Set **only** `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` privately on the **Render API**. Never paste values into the chat, issue, GitHub, terminal output or screenshots. Do not replace `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `REMOTE_SEMANTIC_TOKEN` or existing user data.
4. Allow Render to apply/restart its existing service as needed. Review the **latest deployment's** sanitized startup log for `voice_api_startup_ready=true` and ensure the missing-key warning is absent. If it still reports missing keys, stop; check service scope and nonempty values privately.
5. Sign in as a **verified test user** to the official URL. Check the authenticated `GET /api/voice/status`: it must report `available=true`. Verify that unauthenticated requests return 401. This is still only **configuration readiness**, not a successful call.
6. Start a call with a real iPhone/Android microphone, and confirm named-agent dispatch `aqlyra-voice` and worker job activity in Railway. Do **not** log the 10-minute participant JWT, room metadata, transcripts, document contents or user identifiers. If no job arrives, verify LiveKit project/key/agent-name consistency without creating duplicate resources.
7. Verify one audible STT → existing `execute_chat_turn` → TTS roundtrip, then follow-ups, barge-in and user/session authorization. Only after those tests, record production Voice as accepted.

**Do not enable silent browser Web Speech fallback.** A green build, an authenticated status 200 or a registered worker is not microphone-to-audio E2E proof.

## Minimal real-device acceptance record

Record PASS/FAIL/BLOCKED and device/browser, time, exact frontend/API/worker deployment IDs, no secret values.

| Check | Expected evidence |
| --- | --- |
| Configuration | `voice_api_startup_ready=true`, authenticated available status, correct LiveKit Cloud project |
| English | EN speech → correct transcript → relevant spoken reply |
| Bangla/Banglish | বাংলা / code-switch speech → accurate transcript → clear relevant audio |
| Japanese | 日本語 speech → transcript → corresponding spoken reply |
| Interruptions | Say “stop”, “থামো”, or “止めて” while AI speaks; old speech stops promptly; no overlapping turns |
| Audio lifecycle | iOS/Android permission, enable sound if needed, mute/unmute, hangup releases mic, reconnect after outage |
| Private access | Two independent users; foreign conversation/document ID denied, revoked/disabled users denied |
| Recovery | Invalid provider/session and worker outage fail visibly, never fake a live audio response |
| Persistence | Check authorized conversation history after reconnect; no cross-account disclosure |

Provider-specific native accent **must be listened to**, not inferred from a language selector. Optional validated per-language TTS voice IDs can be reviewed after basic real audio passes.

## Failure response and rollback

- If Render startup readiness remains false, **do not** change Railway, Neon or database settings blindly. Re-check the **two Render key names** and the existing LiveKit project privately.
- If status is true but the worker never joins, leave the app's accurate failure UI enabled; inspect sanitized Railway registration/job errors and LiveKit Cloud project/agent settings. Startup success is not dispatch success.
- If a new voice release is defective, disable the real-time readiness flag through the existing controlled Render configuration workflow and return users to text chat. Retain the previous Vercel/Render/Railway deployment IDs for provider-supported rollback; do not delete production or reset the DB.
- If secrets were exposed anywhere, follow the owner's credential-rotation incident workflow; **never** publish them in the audit record.

## Code and release boundaries

- Existing authoritative Core API: `release/core-without-study-abroad-20261027`. Production UI/worker: `fix/voice-realtime-first-20261102` (PR #90). **Do not merge their divergent whole trees.**
- Dedicated worker: `backend/Dockerfile.voice` → `python -m app.voice.preflight` → `python -m app.voice.worker start`, no public web service. Uses existing private tenant checks and same RAG/chat execution path.
- Two narrow optional security patches: Core [PR #96](https://github.com/naim-munshi/aqlyra-rag-ai/pull/96) and frontend [PR #97](https://github.com/naim-munshi/aqlyra-rag-ai/pull/97) explicitly prevent caching minted room-token responses. Neither patch provides missing credentials.
- No protected `main` merge, new infrastructure, schema migration, secret copy, or production rollout without exact-head CI/review and explicit release authorization.

**Status:** Config BLOCKED until the owner adds matching existing LiveKit Cloud keys to Render. Real iPhone/Android audio and two-user E2E are also BLOCKED until performed. The next operator should not reinterpret a CI PASS as acceptance.
