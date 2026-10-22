#!/usr/bin/env bash
# Start the real Aqlyra application on this Mac only. No public tunnel.
# Safe to re-run: named database/upload volumes are never deleted.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/backend/.env"
export BACKEND_ENV_FILE="./backend/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: Install Docker Desktop first." >&2
  exit 2
fi

if ! docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
  echo "FAIL: Docker Desktop Engine is not running." >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 required for the local security preflight." >&2
  exit 2
fi

if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cp "$ROOT_DIR/backend/.env.example" "$ENV_FILE"
  echo "Created private local development environment."
fi

chmod 600 "$ENV_FILE"

# Replace ONLY the exact example secret; preserve existing custom credentials.
# Never print the generated JWT signing key.
python3 - "$ENV_FILE" <<'PY'
from pathlib import Path
import re
import secrets
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
pattern = r"(?m)^SECRET_KEY=replace-with-a-long-random-secret-key$"
revised, count = re.subn(
    pattern,
    "SECRET_KEY=" + secrets.token_urlsafe(48),
    source,
)
if count:
    path.write_text(revised, encoding="utf-8")
    print("Generated a strong private local JWT key.")
elif not re.search(r"(?m)^SECRET_KEY=\\S{32,}\\s*$", source):
    raise SystemExit("FAIL: Set a strong SECRET_KEY in backend/.env first.")
PY

# Refuse to run plaintext test SMTP against production configuration.
if grep -Eq '^APP_ENV=production([[:space:]]*)$' "$ENV_FILE"; then
  echo "FAIL: backend/.env is marked production; refusing local-mail settings." >&2
  exit 2
fi

dc() {
  docker compose \
    --env-file backend/.env \
    --file docker-compose.yml \
    --file docker-compose.mac-local.yml \
    --profile production "$@"
}

echo "Validating local-only Compose networking..."
dc config --format json | python3 scripts/ops/check_mac_local_compose.py

echo "Starting DB, Redis, local verification inbox, FastAPI and Next.js..."
dc up --detach --build --wait --wait-timeout 600 \
  postgres redis mailpit backend frontend

echo "Checking backend readiness and frontend..."
curl --fail --silent --show-error --max-time 15 \
  http://127.0.0.1:8000/api/v1/readiness
printf '\n'
curl --fail --silent --show-error --max-time 15 \
  --output /dev/null http://127.0.0.1:3000/login
curl --fail --silent --show-error --max-time 15 \
  --output /dev/null http://127.0.0.1:8025/

printf '\nMAC_LOCAL_STACK=READY\n'
echo "Actual application: http://127.0.0.1:3000/login"
echo "Local OTP inbox:    http://127.0.0.1:8025"
echo "LOCAL ONLY. Do not publish this Docker setup to the Internet."
echo "AI/embeddings default to deterministic test providers until configured."
