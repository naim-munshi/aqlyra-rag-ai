#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  pwd
)"

cd "$ROOT_DIR"

if [ "$#" -ne 1 ]; then
  echo "Usage:"
  echo "  $0 backups/<timestamp>"
  exit 2
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
  echo "STOP: backup directory not found"
  exit 1
fi

ENV_FILE="${AQ_ENV_FILE:-$ROOT_DIR/backend/.env}"

DC=(
  docker compose
  --env-file "$ENV_FILE"
)

MANIFEST="$BACKUP_DIR/manifest.json"
DB_DUMP="$BACKUP_DIR/database.dump"
UPLOAD_ARCHIVE="$BACKUP_DIR/uploads.tar.gz"

for file in \
  "$MANIFEST" \
  "$DB_DUMP" \
  "$UPLOAD_ARCHIVE"
do
  if [ ! -f "$file" ]; then
    echo "STOP: missing backup file: $file"
    exit 1
  fi
done


echo "===== CHECKSUM VERIFICATION ====="

python - "$BACKUP_DIR" <<'PY2'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])

manifest = json.loads(
    (root / "manifest.json").read_text(
        encoding="utf-8"
    )
)

if manifest.get("format_version") != 1:
    raise SystemExit(
        "FAIL: unsupported manifest format"
    )

for name in (
    "database.dump",
    "uploads.tar.gz",
):
    expected = (
        manifest["files"][name]["sha256"]
    )

    digest = hashlib.sha256()

    with (root / name).open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    actual = digest.hexdigest()

    if actual != expected:
        raise SystemExit(
            f"FAIL: checksum mismatch: {name}"
        )

print("CHECKSUMS=PASS")
print(
    "ALEMBIC_REVISION="
    + manifest.get(
        "alembic_revision",
        "",
    )
)
PY2


echo
echo "===== UPLOAD ARCHIVE VERIFICATION ====="

tar -tzf "$UPLOAD_ARCHIVE" >/dev/null

echo "UPLOAD_ARCHIVE=PASS"


echo
echo "===== DATABASE ARCHIVE VERIFICATION ====="

"${DC[@]}" up -d postgres >/dev/null

cat "$DB_DUMP" \
  | "${DC[@]}" exec -T postgres \
      pg_restore --list \
      >/dev/null

echo "DATABASE_ARCHIVE=PASS"


echo
echo "===== NON-DESTRUCTIVE RESTORE TEST ====="

VERIFY_DB="aqlyra_verify_$(
  date -u '+%Y%m%d%H%M%S'
)_$$"

cleanup() {
  "${DC[@]}" exec \
    -T \
    -e VERIFY_DB="$VERIFY_DB" \
    postgres \
    sh -lc '
      dropdb \
        -U "$POSTGRES_USER" \
        --if-exists \
        --force \
        "$VERIFY_DB"
    ' \
    >/dev/null 2>&1 || true
}

trap cleanup EXIT

"${DC[@]}" exec \
  -T \
  -e VERIFY_DB="$VERIFY_DB" \
  postgres \
  sh -lc '
    createdb \
      -U "$POSTGRES_USER" \
      "$VERIFY_DB"
  '

cat "$DB_DUMP" \
  | "${DC[@]}" exec \
      -T \
      -e VERIFY_DB="$VERIFY_DB" \
      postgres \
      sh -lc '
        pg_restore \
          -U "$POSTGRES_USER" \
          -d "$VERIFY_DB" \
          --no-owner \
          --no-privileges
      '

RESTORED_REVISION="$(
  "${DC[@]}" exec \
    -T \
    -e VERIFY_DB="$VERIFY_DB" \
    postgres \
    sh -lc '
      psql \
        -U "$POSTGRES_USER" \
        -d "$VERIFY_DB" \
        -Atc "
          SELECT version_num
          FROM alembic_version
          LIMIT 1
        "
    ' | tr -d '\r\n'
)"

EXPECTED_REVISION="$(
  python - "$MANIFEST" <<'PY2'
import json
import sys
from pathlib import Path

manifest = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

print(
    manifest.get(
        "alembic_revision",
        "",
    )
)
PY2
)"

if [ "$RESTORED_REVISION" != "$EXPECTED_REVISION" ]; then
  echo "FAIL: restored Alembic revision mismatch"
  exit 1
fi

echo "DATABASE_RESTORE_TEST=PASS"
echo "RESTORED_ALEMBIC=$RESTORED_REVISION"

echo
echo "BACKUP_VERIFICATION=PASS"
