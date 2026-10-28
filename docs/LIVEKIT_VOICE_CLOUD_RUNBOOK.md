# Aqlyra — LiveKit Cloud voice agent deployment and acceptance (2026-10-28)

## Verified cause: no deployed agents in the owner project

The owner-provided LiveKit Cloud screenshot shows project `aqlyra-rag-ai`
with **"No agents deployed in this project yet"**. Aqlyra's
`POST /api/v1/voice/session` issues room-specific client tokens and the
browser can connect, but there is **no `aqlyra-voice` agent running to
transcribe speech, call Aqlyra RAG, and play spoken replies**.

The code already exists in:
- `backend/app/voice/worker.py`: registered `aqlyra-voice` agent,
  Groq STT, LiveKit Inference TTS, multilingual language detection,
  existing owner-scoped RAG answer generation and transcript persistence
- `backend/Dockerfile.voice`, `backend/requirements-voice.txt`
- `backend/app/services/voice_session_service.py`: authenticated
  short-lived (10-minute) room-specific LiveKit JWT and named agent dispatch
- `frontend/src/components/voice/voice-call-button.tsx`: microphone,
  mute, hangup, audio playback and transcripts

The installed Render **web service is not the LiveKit agent worker**.
Changing `LIVEKIT_URL` alone cannot make AI speech responses work.

## Safe, $0-tier-aware deployment of the existing worker

Official docs:
- https://docs.livekit.io/deploy/agents/quickstart/
- https://docs.livekit.io/reference/developer-tools/livekit-cli/agent/deployment/
- https://docs.livekit.io/deploy/agents/secrets/

LiveKit Build (Free) supports one **production** agent deployment,
with usage/inference quotas; non-production deployment slots are **zero**
on Free. Do not upgrade a plan without the owner's explicit approval.
This procedure operates **only** in the LiveKit project
`aqlyra-rag-ai`; do not deploy a generic Agent Builder template in
place of Aqlyra's existing RAG-backed worker.

1. Confirm the Aqlyra full-release branch has passed exact-head CI
   and its backend dependencies, DB schema and private model provider
   setup are ready. Never provide production DB credentials in GitHub or chat.
2. On an authenticated developer Mac, install/login to the official `lk`
   CLI, then check the target:
   ```bash
   lk cloud auth
   lk project list
   lk project set-default "aqlyra-rag-ai"
   ```
   Verify the **selected project really matches the screenshot**.
3. Build an isolated, secret-free folder from the checked out
   `release/full-with-study-abroad-20261028` repository:
   ```bash
   bash scripts/ops/livekit_voice_bundle.sh
   cd "$HOME/.aqlyra/livekit-voice-agent"
   ```
   This bundles the real `backend/Dockerfile.voice` as `Dockerfile`,
   `app/`, and pinned requirements. It never copies `backend/.env`
   and will refuse to overwrite an existing bundle or upload secrets.
4. Privately create `~/.aqlyra/livekit-agent-secrets.env` (mode 600),
   with **real, non-empty values** appropriate for the isolated
   Neon database, verified email and inference accounts. Required
   backend settings include `SECRET_KEY`, `DATABASE_URL`,
   `REDIS_URL`, `GROQ_API_KEY`, `HF_TOKEN`,
   `GOOGLE_CLIENT_ID`, `RESEND_API_KEY`, `SMTP_FROM_EMAIL`,
   `EMAIL_DELIVERY_PROVIDER=resend`, `LLM_PROVIDER=groq`,
   `EMBEDDING_PROVIDER=huggingface`,
   `RAG_GROUNDING_VERIFIER_ENABLED=true`,
   `RATE_LIMIT_ENABLED=true`,
   `CORS_ORIGINS=https://aqlyra-navy.vercel.app`,
   `APP_ENV=production`, `DEBUG=false`, and
   `VOICE_AGENT_NAME=aqlyra-voice`.
   **No placeholder values.** Do not assume a local Docker
   `localhost` database/Redis URL is cloud-accessible.
   LiveKit Cloud automatically injects `LIVEKIT_URL`,
   `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` into its agent;
   **do not upload those three as LiveKit agent secrets**.
   ```bash
   chmod 600 "$HOME/.aqlyra/livekit-agent-secrets.env"
   ```
   Before using any secret file with the LiveKit CLI, run the new
   **offline/no-network** deployment preflight from the checked-out
   Full Release repository (not the temporary agent bundle):

   ```bash
   python3 scripts/ops/livekit_voice_secrets_preflight.py \
     --secrets-file "$HOME/.aqlyra/livekit-agent-secrets.env"
   ```

   Require `LIVEKIT_SECRETS_PREFLIGHT=PASS` and
   `LIVEKIT_DEPLOYMENT=NOT_RUN`. This check refuses symlinks,
   insecure file modes, placeholders, duplicate/missing keys,
   shell substitutions, localhost/non-TLS DB or Redis targets,
   non-production AI/rate-limit settings and LiveKit-managed
   connection variables; it never prints secret values or calls
   network services. This is a **configuration** check, not proof
   that provider credentials are valid or quotas are available.
   Keep `ARTIFACT_REMOTE_STORAGE_ENABLED=false` until its
   separate real S3 durability acceptance has passed.

5. After ensuring the Free quota and the exact project, explicitly
   deploy the **existing Aqlyra agent**:
   ```bash
   lk agent create --secrets-file "$HOME/.aqlyra/livekit-agent-secrets.env"
   lk agent status
   lk agent logs
   ```
   The CLI writes an agent ID into `livekit.toml` inside the private
   bundle directory for later `lk agent deploy`.
   Do not commit `livekit.toml` or the local secrets file.
6. In the **Render backend environment**, configure the matching
   LiveKit Cloud project's `LIVEKIT_URL` (usually `wss://...`),
   `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` and
   `VOICE_AGENT_NAME=aqlyra-voice`; no values in chat.
   Render must have a healthy real database, Redis, email provider,
   non-deterministic RAG provider and applied schema first.
   On missing credentials the backend appropriately refuses to start.

## Acceptance (record redacted PASS/FAIL, never values or user audio)

- LiveKit dashboard lists **one healthy named `aqlyra-voice` worker**,
  not "No agents deployed".
- Render backend readiness succeeds; protected Vercel site signs in.
- Authenticated browser can grant microphone, receive an agent participant,
  hear a generated response and see transcripts.
- Test Bangla, Japanese and English, one normal conversation and one
  `knowledge` conversation with an owner-owned ready document; observe
  response correctness, grounded citations, state transitions, duration.
- Test mute/unmute, disconnect/hangup, rejoin with a new 10-minute token,
  an unverified account, a foreign user's conversation/document, no
  agent available and provider quota exhausted. Fail safely without
  leaking secrets or private documents.
- Compare Render/LiveKit usage against Free allowances. Suspend worker
  if quota/abuse occurs. Do not expose public calling until these PASS.

**Current status:** no deployed LiveKit agent verified; real two-way call
acceptance is BLOCKED even though offline GitHub voice tests passed.
