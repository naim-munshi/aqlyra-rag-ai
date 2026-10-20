#!/usr/bin/env bash
# Deliberately DESTRUCTIVE: exercise DB + uploads restore only in disposable CI.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [ "${GITHUB_ACTIONS:-}" != "true" ] \
  || [ "${AQ_DISPOSABLE_RESTORE_CONFIRMED:-}" != "yes" ]; then
  echo "REFUSE: disposable restore rehearsal runs only in explicitly opted-in GitHub Actions CI" >&2
  exit 2
fi

# Never use a caller-supplied production environment file.
export AQ_ENV_FILE="$ROOT_DIR/backend/.env.example"
export AQ_BACKUP_ROOT="$(mktemp -d "${RUNNER_TEMP:-/tmp}/aqlyra-restore-ci.XXXXXXXX")"
DC=(docker compose --env-file "$AQ_ENV_FILE")

cleanup() {
  rm -rf -- "$AQ_BACKUP_ROOT"
}
trap cleanup EXIT

echo "===== SEED EPHEMERAL TEST MARKERS ====="

"${DC[@]}" exec -T postgres sh -lc \
  'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE TABLE public.aqlyra_ci_restore_probe (
    id integer PRIMARY KEY,
    marker text NOT NULL
);
INSERT INTO public.aqlyra_ci_restore_probe (id, marker)
VALUES (1, 'before_backup');
SQL

"${DC[@]}" run --rm -T --no-deps \
  --entrypoint sh backend -c \
  'umask 077; printf "%s" "before_backup" > /app/uploads/.aqlyra-ci-restore-probe'

echo "===== CREATE AND VERIFY RESTORABLE BACKUP ====="

scripts/ops/backup.sh

mapfile -t backup_dirs < <(
  find "$AQ_BACKUP_ROOT" -mindepth 1 -maxdepth 1 \
    -type d ! -name '.*' -print
)

if [ "${#backup_dirs[@]}" -ne 1 ]; then
  echo "FAIL: expected one ephemeral backup directory" >&2
  exit 1
fi

backup_dir="${backup_dirs[0]}"
scripts/ops/verify-backup.sh "$backup_dir"

echo "===== CHANGE EPHEMERAL DATA AFTER BACKUP ====="

"${DC[@]}" exec -T postgres sh -lc \
  'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
UPDATE public.aqlyra_ci_restore_probe
SET marker = 'after_backup'
WHERE id = 1;
SQL

"${DC[@]}" run --rm -T --no-deps \
  --entrypoint sh backend -c \
  'printf "%s" "after_backup" > /app/uploads/.aqlyra-ci-restore-probe'

echo "===== REHEARSE DESTRUCTIVE RESTORE ON DISPOSABLE CI DATA ====="

scripts/ops/restore.sh "$backup_dir" --confirm-restore

db_value="$(
  "${DC[@]}" exec -T postgres sh -lc \
    'exec psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT marker FROM public.aqlyra_ci_restore_probe WHERE id = 1"' \
    | tr -d '\r\n'
)"

file_value="$(
  "${DC[@]}" run --rm -T --no-deps \
    --entrypoint sh backend -c \
    'cat /app/uploads/.aqlyra-ci-restore-probe' \
    | tr -d '\r\n'
)"

if [ "$db_value" != "before_backup" ] \
  || [ "$file_value" != "before_backup" ]; then
  echo "FAIL: restored markers differ (DB=$db_value; file=$file_value)" >&2
  exit 1
fi

echo "DISPOSABLE_RESTORE_DB=PASS"
echo "DISPOSABLE_RESTORE_UPLOADS=PASS"
echo "DISPOSABLE_RESTORE_REHEARSAL=PASS"
