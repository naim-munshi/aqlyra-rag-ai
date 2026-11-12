# Aqlyra Voice — LiveKit Cloud Build ($0) deployment

**Status (2026-11-12): prepared and CI-testable, NOT live-deployed.** The old Railway trial expired and the Railway voice worker has no active deployment. This guide preserves Aqlyra's existing FastAPI / Next.js / Neon / Groq / LiveKit architecture. No user data, databases, or production API secrets are modified by this guide.

## Why this hosting option?

LiveKit Cloud Build is $0/month and does not require a credit card. Unlike a 512 MB web-host free instance, it supports purpose-built LiveKit agent deployment. Its **hard monthly ceilings** include **1,000 hosted agent-session minutes**, **5 concurrent hosted agent sessions**, and **$2.50 of LiveKit Inference usage**. Quotas are shared across free projects, and an exhausted allowance causes requests to fail, not unlimited free use. Groq free-tier rate limits also apply. This is appropriate for a free, limited demo, **not unlimited production service**.

The free Build plan can cold-start a hosted worker in **10–20 seconds**, so the frontend now allows **45 seconds** for the agent to join before showing a clear unavailable error. Check actual readiness before calling a voice deployment complete.

Sources (always re-check before deployment):
- [LiveKit pricing](https://livekit.com/pricing)
- [LiveKit free quotas, concurrency, and cold starts](https://docs.livekit.io/deploy/admin/quotas-and-limits/)
- [LiveKit agent deployment guide](https://docs.livekit.io/deploy/agents/quickstart/)
- [LiveKit Cloud secrets](https://docs.livekit.io/deploy/agents/secrets/)

## Account-owner action required

The existing LiveKit Cloud project must be authenticated by its owner. No LiveKit Cloud account/CLI login has been authorized in this assistant session, so no live agent has been created. **Never paste tokens, API secrets, SSH keys, or database URLs into ChatGPT or a GitHub issue.** Only the account owner should select a project and set up secrets.

1. Sign in to [LiveKit Cloud](https://cloud.livekit.io/) and verify the project uses **Build / $0**.
2. Install the official [LiveKit CLI](https://docs.livekit.io/reference/developer-tools/livekit-cli/) on your local machine and run `lk cloud auth`.
3. Run `lk project list` and `lk project set-default "<the EXISTING Aqlyra LiveKit project>"`. Reuse the same project that your production backend's `LIVEKIT_URL` points to. If you choose a new project, first update production backend LiveKit configuration in a controlled separate operation.

## Prepare private runtime settings (never commit)

Create a **private** file outside the repository, for example `~/.config/aqlyra/voice.env`, with values copied securely from the existing valid production environment.

```dotenv
APP_ENV=production
DATABASE_URL=<existing Neon Postgres connection string with SSL>
SECRET_KEY=<existing Aqlyra app secret>
GROQ_API_KEY=<existing Groq API key>
LLM_PROVIDER=groq
VOICE_AGENT_NAME=aqlyra-voice
VOICE_STT_MODEL=whisper-large-v3
VOICE_TTS_MODEL=cartesia/sonic-3.5
VOICE_TTS_DEFAULT_LANGUAGE=en
# Add REDIS_URL and the current RAG, embeddings, memory, and isolation settings
# required by the existing backend (keep identical to the verified environment).
```

**Important:** This snippet is a template, not usable credentials. The worker reads the same user conversations from the existing Neon database; connecting it to a different empty database breaks voice persistence and document access. Verify the cloud egress path, database SSL requirements, and service access. Use only the necessary privileges. The LiveKit Cloud secret store injects `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` automatically: **do not set them in voice.env**.

```bash
chmod 600 ~/.config/aqlyra/voice.env
export AQLYRA_VOICE_SECRETS_FILE="$HOME/.config/aqlyra/voice.env"
```

## Deploy using existing Dockerfile.voice

The repository already contains a separate backend API Dockerfile and voice-worker Dockerfile. The deployment script packages a temporary, minimal build context using **only** `backend/Dockerfile.voice`, `backend/app`, and voice requirements, then runs the official `lk agent` CLI. This avoids any backend service rebuild or duplicate source tree.

From the repository root:

```bash
# First-time registration (pick a suitable region when prompted)
bash scripts/ops/deploy-livekit-cloud-free-voice.sh create

# For later code changes, reuse the saved agent ID/config:
bash scripts/ops/deploy-livekit-cloud-free-voice.sh deploy

# Check worker state:
bash scripts/ops/deploy-livekit-cloud-free-voice.sh status

# Debug logs (CLI uses your authenticated default project)
lk agent logs
```

The agent ID and LiveKit project reference are saved **locally** in `~/.config/aqlyra/livekit-voice.toml` (not in GitHub). The script does not ingest or upload `voice.env` as Docker build context; the LiveKit CLI sends it to the provider's encrypted runtime secrets store. On the free Build plan, create only the normal production agent: **non-production deployments are not included**.

## Production acceptance checklist

1. `lk agent status` shows a deployed agent whose dispatch name is `aqlyra-voice`, and its LiveKit project matches the FastAPI backend's project.
2. An authenticated voice session joins a room. **Do not mistake an established WebRTC room for a connected AI agent.**
3. Validate speech transcription, reply, and TTS playback with a real browser microphone in Bangla, Japanese, English, and code-switching.
4. Verify speaking over the assistant interrupts correctly; document what is supported and what is still limited.
5. Test document-grounded voice without leaking private content across accounts; verify conversation persistence in the original database.
6. Test cold-start behavior and a second simultaneous real user; check LiveKit metrics, session limits, and Groq rate-limit errors.
7. Monitor the Free Build inference/session quota in the LiveKit dashboard. After the monthly cap is exhausted, surface a clear unavailable notice; do not auto-upgrade.

## Why not Render, Koyeb, or Oracle right now?

The old Railway worker peaked around **0.98 GB RAM** in the seven-day operational sample. Render/Koyeb web-service free tiers provide 512 MB and sleep when inactive; that is not a stable match. OCI Ampere A1 **Always Free** is an excellent longer-running alternative (up to 2 OCPUs / 12 GB RAM within current Always Free limits), but requires account verification, available capacity, SSH and server administration. The existing [Oracle deployment guide](ORACLE_ALWAYS_FREE.md) is retained; neither OCI nor Railway changes are made here.

**Security note:** Do not disable protected GitHub branch rules, open database network access publicly without controls, place credentials in git, or upgrade a free account without owner approval. The script is idempotent for subsequent `deploy` runs when its local state file exists, but the first `create` must be run by an authenticated owner.
