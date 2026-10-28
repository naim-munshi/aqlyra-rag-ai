#!/usr/bin/env bash
# RESTORE ONLY TO A THROWAWAY, NETWORK-ISOLATED LOCAL DOCKER CONTAINER.
# Never connects to Neon, changes source database, or publishes host ports.
set -Eeuo pipefail
umask 077

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 <private-backup.dump> <matching-manifest.json>" >&2
  exit 2
fi

BACKUP="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
MANIFEST="$(cd "$(dirname "$2")" && pwd -P)/$(basename "$2")"
[[ -f "$BACKUP" && ! -L "$BACKUP" && -f "$MANIFEST" && ! -L "$MANIFEST" ]] || {
  echo "BLOCKED: require regular backup and manifest files" >&2
  exit 2
}
[[ "$BACKUP" == "$(dirname "$MANIFEST")/"* ]] || {
  echo "BLOCKED: backup and manifest must be stored in the same folder" >&2
  exit 2
}

# Verify archive SHA without printing confidential content.
python3 - "$BACKUP" "$MANIFEST" <<'PY'
import hashlib, json, pathlib, sys
archive, manifest = (pathlib.Path(p) for p in sys.argv[1:])
obj = json.loads(manifest.read_text(encoding="utf-8"))
if (obj.get("format") != "aqlyra-neon-backup.v1"
    or obj.get("archive") != archive.name
    or obj.get("alembic_revision")
        not in {"b5e4a019dc72", "d4ec2f9b7860"}):
    raise SystemExit("BLOCKED: invalid archive manifest")
h = hashlib.sha256()
with archive.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
if h.hexdigest() != obj.get("sha256"):
    raise SystemExit("BLOCKED: backup checksum mismatch")
print("BACKUP_SHA256=PASS")
PY

command -v docker >/dev/null || {
  echo "BLOCKED: Docker is required" >&2
  exit 2
}

IMAGE="pgvector/pgvector:pg18"
CONTAINER="aqlyra-restore-$(date +%s)-$$"
BACKUP_DIR="$(dirname "$BACKUP")"
DUMP_NAME="$(basename "$BACKUP")"
# The password is ONLY for the local disposable database, not Neon.
LOCAL_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# Docker pulls the image before creating the container if necessary.
# --network none, no host port bindings, no remote DB URL, no external secrets.
docker run --detach --rm \
  --name "$CONTAINER" \
  --network none \
  --memory 1536m \
  --cpus 2 \
  -e "POSTGRES_PASSWORD=$LOCAL_PASSWORD" \
  -e "POSTGRES_DB=aqlyra_restore_verify" \
  --mount "type=bind,src=$BACKUP_DIR,dst=/private-backup,readonly" \
  "$IMAGE" >/dev/null

ready=0
for i in $(seq 1 45); do
  if docker exec "$CONTAINER" pg_isready \
       -U postgres -d aqlyra_restore_verify >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "RESTORE_REHEARSAL=BLOCKED database did not start" >&2
  exit 2
fi

# pg_restore restores ONLY into the disposable container created above.
docker exec "$CONTAINER" pg_restore \
  -U postgres -d aqlyra_restore_verify \
  --exit-on-error --no-owner --no-acl \
  "/private-backup/$DUMP_NAME" >/dev/null

revision="$(docker exec "$CONTAINER" psql -X -At \
  -U postgres -d aqlyra_restore_verify \
  -c 'SELECT version_num FROM public.alembic_version' | tr -d '\r\n')"

expected="$(python3 - "$MANIFEST" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["alembic_revision"])
PY
)"
[[ "$revision" == "$expected" ]] || {
  echo "RESTORE_REHEARSAL=BLOCKED revision mismatch" >&2
  exit 2
}

valid="$(docker exec "$CONTAINER" psql -X -At \
  -U postgres -d aqlyra_restore_verify \
  -c "SELECT (to_regclass('public.users') IS NOT NULL AND to_regclass('public.documents') IS NOT NULL AND EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector'))" | tr -d '\r\n')"
[[ "$valid" == "t" ]] || {
  echo "RESTORE_REHEARSAL=BLOCKED core schema/pgvector missing" >&2
  exit 2
}

echo "RESTORE_REHEARSAL=PASS"
echo "RESTORED_ALEMBIC_REVISION=$revision"
echo "LOCAL_DISPOSABLE_DATABASE_REMOVED_ON_EXIT=true"
