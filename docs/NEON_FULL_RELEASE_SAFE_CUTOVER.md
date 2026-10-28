# Aqlyra Full Release — Neon backup, restore rehearsal and controlled migration

**Status (2026-10-28):** Core Render is LIVE and `/api/v1/health` and `/api/v1/readiness`
both returned HTTP 200 from an independent GitHub runner after the owner's
Upstash fix. Full-release schema migration to `d4ec2f9b7860`,
Study Abroad backend cutover, and LiveKit voice agent deployment are NOT
verified complete.

**Never paste Neon, Upstash, Groq, Hugging Face or LiveKit credentials into
ChatGPT, GitHub commits, workflow logs or support tickets.** Only the
owner's trusted local Mac should hold the connection URL.

## 1. Restore correct Neon connector permissions

The current ChatGPT Neon connector is **incorrectly bound to the literal
GitHub repository URL** and rejects project ID `rough-river-66110449`
(`aqlyra-staging`). Reconnect the Neon plugin selecting the actual Neon
project `aqlyra-staging`. The assistant cannot run migrations or create a
snapshot through this mis-scoped connector. Do not guess an alternative
database project or try destructive SQL using the wrong project.

## 2. Read-only isolated database audit

On an authenticated trusted Mac, use the full-release source checked out
from `release/full-with-study-abroad-20261028`. Install dependencies
from the project's pinned backend requirements in an isolated Python
environment as necessary. Ensure `psycopg`, `pg_dump`, `pg_restore`
and Docker are available.

For backup and schema migration, select the **direct/unpooled** Neon
connection in the Neon Connect panel (turn **Pooled connection OFF**).
Neon app traffic may continue using its pooled URL; do not replace the
working Render backend URL just to prepare backups. The backup tool
refuses `-pooler` hostnames in backup mode.

Write the **exact Neon direct DATABASE_URL** only to
`$HOME/.aqlyra/private/neon-url` (mode 600). For example, after copying
the URL to your Mac clipboard in the Neon dashboard:

```bash
cd ~/aqlyra-rag-ai
git fetch origin
git switch release/full-with-study-abroad-20261028
git pull --ff-only origin release/full-with-study-abroad-20261028

umask 077
mkdir -p "$HOME/.aqlyra/private"
chmod 700 "$HOME/.aqlyra/private"
pbpaste > "$HOME/.aqlyra/private/neon-url"
chmod 600 "$HOME/.aqlyra/private/neon-url"
```

**Replace `<NEON-HOST-FROM-DASHBOARD>` with the exact hostname from
the owner's Neon Connect panel, without password, port or protocol:**

```bash
python3 scripts/ops/neon_remote_backup.py \
  --url-file "$HOME/.aqlyra/private/neon-url" \
  --expected-host "<NEON-HOST-FROM-DASHBOARD>"
```

This read-only audit rejects non-Neon hosts, mismatched hostnames,
non-TLS URLs, unreadable/insecure secret files, missing pgvector/core
tables and unexpected Alembic revisions. It reports only whether the
current migration is predecessor `b5e4a019dc72` or full head
`d4ec2f9b7860`. **Never assume `DATABASE_URL` is safe just because
FastAPI returned liveness HTTP 200.**

## 3. Create a local private remote backup (read-only for Neon)

Run the same audit with an explicit private backup directory:

```bash
python3 scripts/ops/neon_remote_backup.py \
  --url-file "$HOME/.aqlyra/private/neon-url" \
  --expected-host "<NEON-HOST-FROM-DASHBOARD>" \
  --backup-dir "$HOME/.aqlyra/private/neon-backups"
```

This generates a custom-format `*.dump` and JSON checksum manifest.
No SQL writes or Alembic commands are executed on Neon. It does **not**
copy the dump to GitHub, Render or a third-party file service.
`BACKUP_STRUCTURAL_CHECK=PASS` verifies archive format only, **not**
restore-ability.

## 4. Rehearse real backup restoration in disposable local Docker

Use the exact backup and matching manifest produced in step 3:

```bash
bash scripts/ops/neon_restore_rehearsal.sh \
  "$HOME/.aqlyra/private/neon-backups/<BACKUP_NAME>.dump" \
  "$HOME/.aqlyra/private/neon-backups/<BACKUP_NAME>.json"
```

The script verifies SHA256, starts a fresh `pgvector/pgvector:pg18`
database with `--network none`, exposes **no host port**, restores
the private dump, checks pgvector, core tables and the Alembic revision,
then destroys the disposable container. This cannot alter Neon, Render
or a persistent local Postgres container. Treat this private restored
data as sensitive. A verified successful run prints
`RESTORE_REHEARSAL=PASS`.

If backup, restore or revision checks fail, **STOP**. Never run an
unreviewed migration or `alembic downgrade`.

## 5. Owner-approved, manual database migration

Only **after** verifying the project, private backup, and successful
isolated restore rehearsal, review the additive full-release migration:
`backend/alembic/versions/d4ec2f9b7860_study_abroad_cases.py`.
The expected predecessor is `b5e4a019dc72` and the expected head is
`d4ec2f9b7860`.

An authenticated owner/operator can run the reviewed Alembic upgrade
**against the correct Neon project** in a controlled maintenance
window. This is a database WRITE and is deliberately not part of the
read-only audit or backup scripts. Do not apply migrations to the
wrong project, automatically at Render startup, or by rebuilding a
Docker image. Re-run step 2 afterward and require
`FULL_RELEASE_SCHEMA=READY`.

## 6. Protected backend and voice cutover (only after above PASS)

In the Render service Settings, change the deploy branch from
`release/core-without-study-abroad-20261027` to
`release/full-with-study-abroad-20261028` without touching env values.
Keep auto-deploy disabled; verify the **exact SHA** and manually deploy.
The existing Render ChatGPT connector has no branch-update action.
Require `/api/v1/health` AND `/api/v1/readiness` to return 200 and
`/api/v1/study-abroad/workflows` to return 200 while anonymous
`/api/v1/study-abroad/cases` returns 401. Test two users, owner-scoped
case/document access, model inference, real email and quota limits.

After this, the LiveKit worker must be deployed by an authenticated
operator to the correct `aqlyra-rag-ai` LiveKit Cloud project with
agent name `aqlyra-voice` using
`docs/LIVEKIT_VOICE_CLOUD_RUNBOOK.md`.
The active frontend is already SSO-protected.
A LiveKit room joining is **not** evidence of an actual voice reply.

Public registration, protected `main` merge, paid upgrades and
publicly readable uploaded documents are **not authorized** by
predeploy CI success alone.
