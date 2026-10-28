#!/usr/bin/env bash
# Prepare a secret-free LiveKit Cloud build context for Aqlyra's existing
# RAG-backed voice worker. Does NOT create/deploy agents or incur cloud cost.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
DEST="${1:-$HOME/.aqlyra/livekit-voice-agent}"

for name in app requirements.txt requirements-voice.txt Dockerfile.voice; do
  test -e "$ROOT/backend/$name" || {
    echo "BLOCKED: missing Aqlyra voice source: backend/$name" >&2
    exit 2
  }
done

if [[ -e "$DEST" ]]; then
  echo "BLOCKED: deployment context already exists; refusing to overwrite: $DEST" >&2
  exit 2
fi

mkdir -p "$(dirname "$DEST")"
STAGING="$(mktemp -d "$(dirname "$DEST")/.aqlyra-voice-bundle.XXXXXXXX")"
trap 'rm -rf "$STAGING"' EXIT

cp -R "$ROOT/backend/app" "$STAGING/app"
cp "$ROOT/backend/requirements.txt" "$STAGING/requirements.txt"
cp "$ROOT/backend/requirements-voice.txt" "$STAGING/requirements-voice.txt"
cp "$ROOT/backend/Dockerfile.voice" "$STAGING/Dockerfile"

cat >"$STAGING/.dockerignore" <<'IGNORE'
.env
.env.*
*.pem
*.key
*.p12
*.pfx
*secrets*
__pycache__
*.pyc
.git
.gitignore
reports
uploads
IGNORE

# Never ship developer environments, credentials, or private local uploads.
if find "$STAGING/app" -type f \
  \( -name '.env' -o -name '.env.*' -o -name '*.pem' \
     -o -name '*.key' -o -name '*secret*' \) | grep -q .; then
  echo "BLOCKED: local voice source contains a secret-like filename" >&2
  exit 3
fi

mv "$STAGING" "$DEST"
trap - EXIT

echo "PASS: secret-free Aqlyra LiveKit worker context prepared at $DEST"
echo "NEXT: authenticate LiveKit, select aqlyra-rag-ai, and deploy with"
echo "      a separate owner-managed chmod-600 secrets file."
echo "      FIRST: python3 scripts/ops/livekit_voice_secrets_preflight.py"
echo "             --secrets-file PRIVATE_OWNER_FILE (run from source checkout)."
echo "      Follow docs/LIVEKIT_VOICE_CLOUD_RUNBOOK.md."
