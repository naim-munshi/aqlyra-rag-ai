#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  pwd
)"

cd "$ROOT_DIR"

PYTHON_BIN="${AQ_PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "STOP: Python 3 interpreter not found"
    exit 1
  fi
fi

ENV_FILE="${AQ_ENV_FILE:-$ROOT_DIR/backend/.env}"
BACKUP_ROOT="${AQ_BACKUP_ROOT:-$ROOT_DIR/backups}"

DC=(
  docker compose
  --env-file "$ENV_FILE"
)

timestamp="$(
  date -u '+%Y%m%dT%H%M%SZ'
)"

final_dir="$BACKUP_ROOT/$timestamp"
partial_dir="$BACKUP_ROOT/.${timestamp}.partial"

mkdir -p "$BACKUP_ROOT"

if [ -e "$final_dir" ] || [ -e "$partial_dir" ]; then
  echo "STOP: backup directory already exists"
  exit 1
fi

mkdir -p "$partial_dir"

backend_was_running=0
voice_was_running=0
maintenance_started=0


is_running() {
  local service="$1"
  local cid

  cid="$("${DC[@]}" ps -q "$service" 2>/dev/null || true)"

  if [ -z "$cid" ]; then
    return 1
  fi

  [ "$(
    docker inspect \
      --format '{{.State.Running}}' \
      "$cid" 2>/dev/null || true
  )" = "true" ]
}


wait_for_backend() {
  local i
  local cid
  local state

  for i in $(seq 1 45); do
    cid="$("${DC[@]}" ps -q backend 2>/dev/null || true)"

    if [ -n "$cid" ]; then
      state="$(
        docker inspect \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
          "$cid" 2>/dev/null || true
      )"

      if [ "$state" = "healthy" ]; then
        return 0
      fi
    fi

    sleep 2
  done

  echo "WARNING: backend did not become healthy automatically" >&2
  return 1
}


cleanup() {
  local exit_code=$?

  trap - EXIT

  if [ "$exit_code" -ne 0 ]; then
    rm -rf "$partial_dir"
  fi

  if [ "$maintenance_started" -eq 1 ]; then
    if [ "$backend_was_running" -eq 1 ]; then
      "${DC[@]}" start backend >/dev/null 2>&1 || true
      wait_for_backend >/dev/null 2>&1 || true
    fi

    if [ "$voice_was_running" -eq 1 ]; then
      "${DC[@]}" start voice-worker >/dev/null 2>&1 || true
    fi
  fi

  exit "$exit_code"
}

trap cleanup EXIT


echo "===== BACKUP PREFLIGHT ====="

"${DC[@]}" up -d postgres >/dev/null

"${DC[@]}" exec -T postgres \
  sh -lc '
    command -v pg_dump >/dev/null
    command -v pg_restore >/dev/null
  '

"${DC[@]}" run \
  --rm \
  -T \
  --no-deps \
  --entrypoint sh \
  backend \
  -lc 'command -v tar >/dev/null'


if is_running backend; then
  backend_was_running=1
fi

if is_running voice-worker; then
  voice_was_running=1
fi


database_name="$(
  "${DC[@]}" exec -T postgres \
    sh -lc 'printf "%s" "$POSTGRES_DB"'
)"

alembic_revision="$(
  "${DC[@]}" exec -T postgres \
    sh -lc '
      psql \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -Atc "
          SELECT version_num
          FROM alembic_version
          LIMIT 1
        "
    ' | tr -d '\r\n'
)"

git_commit="$(
  git rev-parse HEAD
)"


echo "===== ENTER MAINTENANCE WINDOW ====="

services=()

if [ "$backend_was_running" -eq 1 ]; then
  services+=(backend)
fi

if [ "$voice_was_running" -eq 1 ]; then
  services+=(voice-worker)
fi

if [ "${#services[@]}" -gt 0 ]; then
  "${DC[@]}" stop "${services[@]}" >/dev/null
fi

maintenance_started=1


echo "===== DATABASE DUMP ====="

"${DC[@]}" exec -T postgres \
  sh -lc '
    exec pg_dump \
      -U "$POSTGRES_USER" \
      -d "$POSTGRES_DB" \
      -Fc \
      --no-owner \
      --no-privileges
  ' \
  > "$partial_dir/database.dump"


echo "===== UPLOAD ARCHIVE ====="

"${DC[@]}" run \
  --rm \
  -T \
  --no-deps \
  --entrypoint sh \
  backend \
  -lc '
    exec tar \
      -C /app/uploads \
      -czf - \
      .
  ' \
  > "$partial_dir/uploads.tar.gz"


echo "===== MANIFEST ====="

export AQ_MANIFEST_DIR="$partial_dir"
export AQ_DATABASE_NAME="$database_name"
export AQ_ALEMBIC_REVISION="$alembic_revision"
export AQ_GIT_COMMIT="$git_commit"

"$PYTHON_BIN" - <<'PY2'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["AQ_MANIFEST_DIR"])

files = {}

for name in (
    "database.dump",
    "uploads.tar.gz",
):
    path = root / name

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    files[name] = {
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }

manifest = {
    "format_version": 1,
    "created_at": datetime.now(
        timezone.utc
    ).isoformat(),
    "git_commit": os.environ["AQ_GIT_COMMIT"],
    "database": os.environ["AQ_DATABASE_NAME"],
    "alembic_revision": (
        os.environ["AQ_ALEMBIC_REVISION"]
    ),
    "files": files,
}

(root / "manifest.json").write_text(
    json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY2


mv "$partial_dir" "$final_dir"

echo
echo "BACKUP_STATUS=PASS"
echo "BACKUP_DIR=$final_dir"
