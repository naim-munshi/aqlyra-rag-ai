# Aqlyra Full Release — Neon backup, restore rehearsal and controlled migration

**Verified Core staging state (2026-10-28):** Neon project
`rough-river-66110449` (`aqlyra-staging`), default branch
`production` (`br-morning-water-a1lgl3s4`), database `neondb`
and role `neondb_owner` were independently checked. Core's one-time
schema bootstrap has **already succeeded**: `alembic_version=b5e4a019dc72`,
16 application tables, pgvector installed, users=0, documents=0.
Render Core-only deployment `dep-dbgo7nh42hec73dkfc4g`, SHA
`dc3920fb1428e143b8c393fd25941f7206c35b4c` remains live,
auto-deploy OFF, with prior fixed-origin `/health` and `/readiness`
HTTP 200. DATABASE_MIGRATION_MODE was returned to `manual`.

**Recovery truth:** The pre-bootstrap snapshot
`snap-restless-mouse-a144fpzy` captures an EMPTY schema. A second
no-compute, non-default protective branch `backup-core-schema-20261028`
(`br-damp-credit-a1mksvnz`) captures the migrated Core state and
must not be deleted. It has no compute endpoint; it has **not**
been independently restored. The default branch snapshot schedule
was empty on the last provider inspection. These resources are NOT
a verified off-host backup or routine backup schedule.

**Safe synthetic acceptance:** Existing GitHub Actions Python 3.13
PostgreSQL 16 and 18 matrix successfully executed Full migration,
a synthetic custom-format pg_dump, and isolated networkless PG18 Docker
restore. This proves local recovery plumbing, **not** a restore of
the live Neon database. On 2026-10-28, the owner created a private real-Neon pg_dump and matching SHA-256 manifest, then successfully restored that exact archive in isolated networkless PG18 Docker (RESTORE_REHEARSAL=PASS, revision b5e4a019dc72, disposable container cleanup). The all-in-one wrapper was interrupted because Docker was initially stopped; the owner completed its restore step separately. Independent live read-only Neon postflight verified the same Core revision and zero users/documents. This proves database recovery, NOT uploaded-file or S3 object recovery. Preserve the private archive off-repository.

**Remaining migrations:** Do not repeat Core bootstrap or reset the
database. Only the additive, owner-approved Full Release migration
`b5e4a019dc72 -> d4ec2f9b7860` remains. It creates four private
Study Abroad tables. The protected frontend, Core backend and main
branch must remain untouched while preparing recovery.

**Never paste Neon, Upstash, Groq, Hugging Face or LiveKit credentials into
ChatGPT, GitHub commits, workflow logs or support tickets.** Only the
owner's trusted local Mac should hold the connection URL.

## 1. Reverify scope without changing live resources

The connected Neon project is already correctly scoped and the Core
database is initialized. Recheck the exact branch, database, role,
current Alembic head, user/document counts and provider recovery
resources immediately before any local backup. Do not create a
second staging project, repeat migrations, alter Render credentials,
reset data, or assume the no-compute branch is an independently
tested restore. The pre-bootstrap snapshot and Core recovery branch
must be preserved.

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

Store the **exact Neon direct DATABASE_URL** only in
`$HOME/.aqlyra/private/neon-url` (mode 600); the owner has already
created and validated this file. Do not overwrite it from a stale
clipboard or display its contents in the terminal. On the existing Mac
recovery worktree, prepare the reviewed source and toolchain:

```bash
# Use the separate owner recovery worktree; never reset the original repo.
cd "$HOME/aqlyra-full-recovery"
git fetch origin release/full-with-study-abroad-20261028
git switch --detach origin/release/full-with-study-abroad-20261028

source "$HOME/.aqlyra/recovery-venv/bin/activate"
export PATH="$(brew --prefix libpq)/bin:$PATH"

# Existing owner-only direct URL must already be present.
test -s "$HOME/.aqlyra/private/neon-url"
test "$(stat -f '%Lp' "$HOME/.aqlyra/private/neon-url")" = 600
```

**Replace `<NEON-HOST-FROM-DASHBOARD>` with the exact hostname from
the owner's Neon Connect panel, without password, port or protocol:**

```bash
python3 scripts/ops/neon_remote_backup.py \
  --url-file "$HOME/.aqlyra/private/neon-url" \
  --expected-host "<NEON-HOST-FROM-DASHBOARD>" \
  --expected-database neondb \
  --expected-role neondb_owner
```

The `--expected-database` and `--expected-role` arguments are mandatory:
both the submitted PostgreSQL URL and the connected session are checked
against the independently inspected Neon database/role. If the approved role
changes, re-verify it through Neon before editing the command; never guess.
This is a read-only identity check, not a backup or migration.

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
  --expected-database neondb \
  --expected-role neondb_owner \
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

Before reporting success, the rehearsal verifies the **actual** Full Release
Study Abroad tables against Alembic revision `d4ec2f9b7860`; it also
rejects a supposedly Core-only restored revision `b5e4a019dc72` if any
unexpected Study Abroad table exists. The revision label alone is insufficient.

The script verifies SHA256, starts a fresh `pgvector/pgvector:pg18`
database with `--network none`, exposes **no host port**, restores
the private dump, checks pgvector, core tables and the Alembic revision,
then destroys the disposable container. This cannot alter Neon, Render
or a persistent local Postgres container. Treat this private restored
data as sensitive. A verified successful run prints
`RESTORE_REHEARSAL=PASS`.

If backup, restore or revision checks fail, **STOP**. Never run an
unreviewed migration or `alembic downgrade`.

## 4A. Recommended single-command private recovery gate (operator Mac)

Instead of manually matching archive filenames from sections 2–4,
the reviewed script now performs **both** required read-only Neon
identity/schema checks, creates a new private non-overwriting
custom-format backup, restores it in networkless disposable Docker,
and rechecks the live Core revision. It makes **no** production schema
changes and does not run Alembic upgrade:

```bash
bash scripts/ops/neon_full_release_recovery_gate.sh \
  --url-file "$HOME/.aqlyra/private/neon-url" \
  --expected-host "<DIRECT-NEON-HOST-FROM-DASHBOARD>" \
  --expected-database neondb \
  --expected-role neondb_owner \
  --backup-root "$HOME/.aqlyra/private/neon-backups"
```

**Exact prerequisites:** owner-only `0600` URL file (never commit it),
direct unpooled Neon connection, existing 0700 backup directory (or
new empty directory), local Python environment with `psycopg`,
PostgreSQL 18-compatible `pg_dump` and `pg_restore`, and Docker
Desktop running. Neon currently runs PostgreSQL 18.6: pg_dump 16.x is
incompatible with the newer server. The recovery preflight now checks
both PostgreSQL client versions and reports a sanitized mismatch before
a dump is created. The Mac operator should confirm pg_dump and pg_restore
are 18.x, selecting Homebrew libpq before any older PostgreSQL clients.
No other Homebrew tap needs to be trusted. Existing shell and safety tests validate syntax and
negative cases in CI. The script refuses wrong DB/role, wrong revision,
insecure permissions and mismatched archives. A successful run prints
`NEON_PRIVATE_BACKUP=PASS`,
`NEON_ISOLATED_RESTORE=PASS`,
`FULL_RELEASE_DATABASE_MIGRATION=NOT_RUN`.
The private backup remains only on the operator's Mac; it must be
protected and retained under the owner's recovery policy. Do not
paste its files, URLs, credentials or user data into chat or GitHub.

The owner's real private Neon backup and separate isolated restore PASS evidence are recorded in PR #37. The all-in-one script did not itself exit 0 when Docker was stopped, but the constituent restoration was subsequently completed, and live schema postflight was independently verified. Synthetic CI results alone do not satisfy this check. Keep protected Vercel SSO on.

## 4B. Read-only exact Core/Full schema audit

An independent fail-closed schema audit requires exactly 16 Core public
tables before migration, or 20 after the approved Full migration.
The Full phase additionally checks five cascading Study Abroad foreign
keys and three reviewed indexes, along with the matching Alembic head.
It opens a read-only transaction and never performs database DDL or DML.

Before any separately approved production schema write, from the
owner's Full Release worktree:

```bash
python3 scripts/ops/neon_study_schema_audit.py \
  --url-file "$HOME/.aqlyra/private/neon-url" \
  --expected-host "ep-calm-resonance-a17kpw1l.ap-southeast-1.aws.neon.tech" \
  --expected-database neondb --expected-role neondb_owner \
  --expected-phase core
```

Core acceptance requires `NEON_SCHEMA_TABLES=PASS`,
`NEON_TABLE_COUNT=16`, and `ALEMBIC_REVISION=b5e4a019dc72`.
Only after approved migration, repeat with `--expected-phase full` and
require `NEON_STUDY_FK_INDEX=PASS`, `NEON_TABLE_COUNT=20`, and
`ALEMBIC_REVISION=d4ec2f9b7860`.
Neither result proves authenticated production RAG/Study Abroad E2E.
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
