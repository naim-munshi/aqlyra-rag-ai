#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  pwd
)"

cd "$ROOT_DIR"

if [ "$#" -ne 2 ] || [ "$2" != "--confirm-restore" ]; then
  echo "Usage:"
  echo "  $0 backups/<timestamp> --confirm-restore"
  echo
  echo "This operation REPLACES the current database"
  echo "and uploaded document storage."
  exit 2
fi

BACKUP_DIR="$1"
ENV_FILE="${AQ_ENV_FILE:-$ROOT_DIR/backend/.env}"

DC=(
  docker compose
  --env-file "$ENV_FILE"
)

DB_DUMP="$BACKUP_DIR/database.dump"
UPLOAD_ARCHIVE="$BACKUP_DIR/uploads.tar.gz"


echo "===== VERIFY BACKUP FIRST ====="

"$ROOT_DIR/scripts/ops/verify-backup.sh" \
  "$BACKUP_DIR"


echo
echo "===== STOP APPLICATION SERVICES ====="

# An optional voice worker may not be configured in a staging environment.
# Only restart it if it was running before the restore.
voice_worker_was_running=0
voice_cid="$("${DC[@]}" ps -q voice-worker 2>/dev/null || true)"
if [ -n "$voice_cid" ] && \
   [ "$(docker inspect --format '{{.State.Running}}' "$voice_cid" \
       2>/dev/null || true)" = "true" ]; then
  voice_worker_was_running=1
fi

"${DC[@]}" stop \
  backend \
  voice-worker


echo
echo "===== RESTORE DATABASE ====="

cat "$DB_DUMP" \
  | "${DC[@]}" exec -T postgres \
      sh -lc '
        set -e

        dropdb \
          -U "$POSTGRES_USER" \
          --if-exists \
          --force \
          "$POSTGRES_DB"

        createdb \
          -U "$POSTGRES_USER" \
          "$POSTGRES_DB"

        pg_restore \
          -U "$POSTGRES_USER" \
          -d "$POSTGRES_DB" \
          --no-owner \
          --no-privileges
      '


echo
echo "===== RESTORE UPLOADS ====="

cat "$UPLOAD_ARCHIVE" \
  | "${DC[@]}" run \
      --rm \
      -T \
      --no-deps \
      --entrypoint sh \
      backend \
      -lc '
        set -e

        find /app/uploads \
          -mindepth 1 \
          -maxdepth 1 \
          -exec rm -rf -- {} +

        tar \
          -C /app/uploads \
          -xzf -
      '


echo
echo "===== START APPLICATION ====="

"${DC[@]}" up -d backend

if [ "$voice_worker_was_running" -eq 1 ]; then
  "${DC[@]}" up -d voice-worker
else
  echo "Voice worker was not running before restore; leaving it stopped."
fi


echo
echo "===== WAIT FOR READINESS ====="

ready=0

for i in $(seq 1 45); do
  if curl \
    -fsS \
    http://127.0.0.1:8000/api/v1/readiness \
    >/dev/null 2>&1
  then
    ready=1
    break
  fi

  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "FAIL: backend did not become ready"
  echo "Application services remain running for inspection."
  exit 1
fi

curl -fsS \
  http://127.0.0.1:8000/api/v1/health
echo

curl -fsS \
  http://127.0.0.1:8000/api/v1/readiness
echo

echo
echo "RESTORE_STATUS=PASS"
