# Aqlyra Voice — deployment and safety

## Preserve the existing architecture

- Official frontend: Vercel. Production API, RAG/retrieval, authentication and conversations: existing Render backend.
- Database: the existing, already migrated production PostgreSQL/pgvector instance. Redis: the existing production service. No new Railway database or second chat brain is required for voice.
- Dedicated LiveKit worker: runs `backend/app/voice/worker.py` using `backend/Dockerfile.voice`. It calls the existing `execute_chat_turn`, authorization and conversation persistence; it is not an independent assistant.
- **Keep `VOICE_AGENT_READY=false` on the API until a registered voice worker has passed authenticated two-way audio and security acceptance.**

## Verified staging state

Railway project `Aqlyra-Staging` has an **unapplied** `aqlyra-voice-worker` service. Its LiveKit/Groq variables are **staged, not live**. It has no successful deployment. Required production dependencies `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` and `EMBEDDING_PROVIDER` have not all been verified on that worker.

The Railway environment has one shared pending patch that also creates unrelated frontend, backend, database and storage resources. **Do not use Accept/Deploy Changes on that entire patch just to deploy voice.** Resource limits and possible billing are separate gates. Never reset a DB, migrate production, publish secrets or merge protected `main` to work around this.

## Provider configuration

- LiveKit Cloud Build free tier: https://cloud.livekit.io and https://livekit.com/pricing . Confirm project quotas and billing before releasing; real STT/TTS inference may consume usage credits.
- GroqCloud: https://console.groq.com . The existing Aqlyra chat/RAG brain can use Groq `openai/gpt-oss-20b` when configured; quota limits still apply.
- Default LiveKit speech chain in this branch: `deepgram/nova-3` STT, `openai/gpt-oss-120b` session plumbing, and `cartesia/sonic-3` TTS. Actual answers continue to come from `execute_chat_turn`.
- Embedding configuration **must match the current production API exactly**: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, and required provider credentials. Never replace the index model or assume that a new 384-dimensional model is compatible with stored vectors.
- The worker must use the same existing `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY` as the API, with safe connection-pool limits. Configure only through the target provider's secret store; never commit them.

## Two supported deployment routes

**Railway (original plan):** Deploy only the preconfigured dedicated worker, not the full mixed staging patch. Railway has the LiveKit/Groq values *staged*, but those values do not automatically exist in GitHub Actions, LiveKit Cloud, or Render. The resource limit and missing database/Redis/embedding configuration still block Railway worker release.

**LiveKit Cloud (isolated alternative):** This avoids provisioning the unrelated Railway services. The branch-only GitHub workflow `.github/workflows/livekit-voice-deploy.yml` runs source/packaging tests on push. Cloud release is **explicitly manual**, and the `create` operation requires a supported `region` while `deploy` requires an existing `agent_id`. It uses a GitHub environment `livekit-voice-staging` and expects the required secrets/variables to be present there; it **cannot extract** the staged Railway secrets.

- GitHub secrets for this route: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GROQ_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, and whichever embedding credential the production API uses. GitHub variables: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `VOICE_TTS_VOICE`.
- `python backend/scripts/prepare_livekit_context.py OUTPUT_DIRECTORY` creates an isolated cloud build context, renaming the voice-specific Dockerfile to `Dockerfile` and copying only the app and dependencies. It never copies `.env` files, uploads, databases or the API Dockerfile.
- LiveKit Cloud automatically injects its own `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` into cloud agent containers; the workflow omits them from the LiveKit runtime secrets file. The GitHub credentials are only used to authorize the CLI.
- LiveKit CLI uses `livekit.toml` for existing agent identification; its `create` command generates that file and an agent ID. `backend/livekit.yaml` was an unsupported file and has been removed. The workflow uses `--id` explicitly for later deploys, so there is no risk of selecting an arbitrary agent.
- The branch workflow does **not** run cloud deploy automatically. GitHub's manual workflow UI may require it to exist on the repository default branch; **do not merge `main` merely to run this workflow**. Release approval, secrets and run availability must be verified before deployment.

Official docs: https://docs.livekit.io/reference/developer-tools/livekit-cli/agent/deployment/ and https://docs.livekit.io/deploy/agents/builds/ and https://docs.livekit.io/deploy/agents/secrets/ .

## Verification gates

1. Offline preflight and GitHub CI must PASS at the exact release commit. A passing configuration-only preflight does **not** prove actual cloud connectivity.
2. Dedicated agent is independently running and registered under `aqlyra-voice`; inspect provider logs and status without printing secrets.
3. Authenticated users pass real speech round trip, including English, Bangla and Japanese, on iOS and Android; revoked accounts/foreign documents are denied. Test STT→Aqlyra RAG→TTS, interruptions, mute/hangup, permissions and fallback.
4. Confirm quotas/costs, network and database/Redis reachability, secrets isolation and rollback. Only then enable the API readiness flag under the approved rollout.

The browser speech fallback is not a substitute for full LiveKit WebRTC acceptance. Until the gates pass, describe voice as **code-ready / live audio unverified**, not a completed production launch.
