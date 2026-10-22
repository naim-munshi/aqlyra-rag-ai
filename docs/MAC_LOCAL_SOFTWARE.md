# Aqlyra full software on macOS — local private startup

Use this when Docker Desktop is running on your Mac and you want the
**actual** Next.js + FastAPI + PostgreSQL/pgvector + Redis application,
not the publicly hosted scripted portfolio preview.

This deployment is **local to your computer only** and is not safe to
publish through Tailscale Funnel, Cloudflare Tunnel, port-forwarding,
or an Internet-facing reverse proxy.

## Start with one command

```bash
cd ~/aqlyra-rag-ai
git pull --ff-only origin main
bash scripts/ops/mac_local_up.sh
```

If the repository does not exist yet:

```bash
cd ~
git clone https://github.com/naim-munshi/aqlyra-rag-ai.git
cd aqlyra-rag-ai
bash scripts/ops/mac_local_up.sh
```

**Requirements:** Docker Desktop Engine running, Docker Compose v2,
Python 3, Git, and free disk for Python/Node images. The script uses
the existing backend and frontend Dockerfiles; Node.js does not need
to be installed on the host.

The script:
1. Creates `backend/.env` only when missing, without overwriting existing
   secrets; replaces exactly the repository's known placeholder
   `SECRET_KEY` with a private random key; sets mode 600.
2. Rejects a production-marked environment and verifies the full
   Docker configuration binds its local services to loopback only.
3. Builds and starts **PostgreSQL/pgvector, Redis, FastAPI, Next.js**
   and the **Mailpit** local SMTP inbox, using the existing persistent
   PostgreSQL and document volumes.
4. Waits for Docker health checks and tests the backend readiness,
   login HTML, and local inbox.

No database or upload volume is wiped, and no paid cloud resource is
created. Existing non-placeholder configuration and credentials stay
unchanged.


## Recover a diverged Mac checkout without rewriting Git history

When `git pull --ff-only origin main` fails because the local branch has
diverged, **do not** run `git reset --hard`, force-pull, or delete the
existing checkout. You can run the reviewed current `main` in a separate
detached worktree without rewriting the original repository:

```bash
cd ~/aqlyra-rag-ai
git status --short --branch
git fetch origin main
git worktree list

# Only create a fresh worktree when the destination does not yet exist.
if [ ! -e "$HOME/aqlyra-rag-ai-live" ]; then
  git worktree add --detach "$HOME/aqlyra-rag-ai-live" origin/main
fi

cd ~/aqlyra-rag-ai-live
git log -1 --format='%h %s'
test -f scripts/ops/mac_local_up.sh
```

Verify that the displayed commit matches the reviewed GitHub main
before starting. If `~/aqlyra-rag-ai-live` already exists, do not
blindly reuse it; inspect `git status`, `git rev-parse HEAD`, and
`git worktree list` instead. The worktree shares Git objects but does
not overwrite the original worktree's files, branch or uncommitted edits.

**Important: Docker Compose project identity and existing data.**
By default Compose derives its project name from the checkout directory:
`aqlyra-rag-ai` and `aqlyra-rag-ai-live` can use *different*
`postgres_data` and `uploads_data` volumes. That isolation keeps the
original data untouched but means the new worktree might appear to have
an empty database. The app's fixed container names can also conflict
with running containers from the original checkout. Before startup,
inspect without stopping or removing anything:

```bash
docker ps -a --filter 'name=aqlyra-' --format '{{.Names}} {{.Status}}'
docker volume ls --format '{{.Name}}' | grep 'aqlyra' || true
```

If old Aqlyra containers (including stopped ones) exist, stop here and resolve the
container-name collision deliberately; do not delete or prune containers
or volumes. For a new, isolated local instance, after checking that no
old services are in the way, run `bash scripts/ops/mac_local_up.sh`
from the new worktree. Its `backend/.env` is also separate from the
original checkout's `backend/.env`.

Do **not** set `COMPOSE_PROJECT_NAME` to the original project's name
merely to make data appear in the new worktree. Doing so may attach
the new application code to an existing database and automatically run
Alembic migrations against it. Reuse an existing project/volume only
after identifying its owner, making a verified backup and reviewing
migration compatibility. Never run `docker compose down -v`,
`docker volume prune` or destructive Git cleanup as a recovery shortcut.

## Open the real software

- **Login:** <http://127.0.0.1:3000/login>
- **Register:** <http://127.0.0.1:3000/register>
- **Verification inbox:** <http://127.0.0.1:8025>
- **Backend readiness:** <http://127.0.0.1:8000/api/v1/readiness>

Register using a test email address. The backend creates an actual
verification challenge and delivers its email to **Mailpit**, which
intercepts test mail on your Mac. Read the six-digit code in
`http://127.0.0.1:8025`, enter it on Aqlyra's verification page,
and verify you can log in and reach the actual authenticated workspace.
No verification email is delivered to a real external mailbox in this
environment.

Mailpit's SMTP server has **fake/insecure authentication** on the
private Docker network specifically for local testing. Port 1025
is **not** published to the host; only the test inbox UI is exposed
on `127.0.0.1:8025`. The local Compose overlay deliberately keeps
FastAPI, frontend, Postgres and Mailpit bound to loopback. The app's
production configuration always requires SMTP TLS.

## AI capabilities are separate from infrastructure readiness

Initial `backend/.env` config selects deterministic test embeddings
and a deterministic LLM. Real database/auth/document endpoints are
running, **but deterministic outputs do not demonstrate genuine model
inference or semantic retrieval**.

Before claiming real RAG/AI capabilities, configure genuine LLM and
embedding providers in your private environment. Keep compatible
384-dimensional embedding configuration, use dedicated test
documents and verify citation grounding and refusal behavior.
Never share credentials in chat, screenshots, or GitHub.

Google login additionally needs matching Google Client IDs.
Realtime voice requires an active LiveKit configuration and voice
worker. These integrations are not enabled by this local script.

## Troubleshooting without losing data

From the repository root:

```bash
docker compose \
  --env-file backend/.env \
  -f docker-compose.yml \
  -f docker-compose.mac-local.yml \
  --profile production ps

docker compose \
  --env-file backend/.env \
  -f docker-compose.yml \
  -f docker-compose.mac-local.yml \
  --profile production logs --no-color --tail 80 backend frontend mailpit
```

If localhost port 3000, 8000, 5432, or 8025 is already taken by a
different process, do not kill or delete unrelated services blindly.
Inspect conflicts first. The startup script is safe to rerun.

Never run `docker compose down -v`, `docker volume prune`,
or `docker system prune --volumes` to troubleshoot; those can
destroy the database or uploads.

## Public hosting is a different release gate

Your `aqlyrax.vercel.app` frontend is **not connected** to this local
FastAPI instance. It remains the labelled demo until there is
a hardened, authenticated HTTPS backend with a reachable database,
persistent private uploads, rate limits, real SMTP and provider
credentials. Do not expose the local test Mailpit inbox, Docker DB
ports, or deterministic fake model mode to the Internet.

The next release step after successfully testing local registration,
login, upload and retrieval is a separate production-grade Mac hosting
profile or a verified Always Free cloud VM. Consult
[STAGING.md](STAGING.md) for full acceptance criteria.
