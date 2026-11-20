#!/usr/bin/env bash
# Deploy the existing Aqlyra LiveKit voice worker to LiveKit Cloud Build.
# No secrets or generated agent credentials are committed to the repository.
set -euo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage: AQLYRA_VOICE_SECRETS_FILE=/private/path/voice.env \
         bash scripts/ops/deploy-livekit-cloud-free-voice.sh create|deploy|status

Prerequisites:
  * LiveKit CLI installed; run 'lk cloud auth' and set the correct default project.
  * Create a private voice.env outside this Git repository, with DATABASE_URL,
    GROQ_API_KEY, SECRET_KEY, and other backend settings required by your RAG.
  * Do not add LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET to voice.env:
    LiveKit Cloud injects credentials for the selected project.

Optional: AQLYRA_LIVEKIT_REGION (when creating, e.g. asia-southeast)
State: ${HOME}/.config/aqlyra/livekit-voice.toml (not a secret).
EOF
}

if [[ "$#" -ne 1 ]]; then
  usage >&2
  exit 2
fi
action="$1"
case "$action" in
  create|deploy|status) ;;
  *) usage >&2; exit 2 ;;
esac

command -v lk >/dev/null 2>&1 || {
  echo "LiveKit CLI 'lk' was not found; install it and run 'lk cloud auth'." >&2
  exit 1
}

state_dir="${HOME}/.config/aqlyra"
state_file="${state_dir}/livekit-voice.toml"

# Never follow a user-controlled symlink for saved deployment state.
if [[ -L "$state_dir" || -L "$state_file" ]]; then
  echo "Refusing symlinked LiveKit state path." >&2
  exit 1
fi
if [[ -e "$state_file" && ! -f "$state_file" ]]; then
  echo "LiveKit state path must be a regular file." >&2
  exit 1
fi

if [[ "$action" == status ]]; then
  [[ -f "$state_file" ]] || {
    echo "No saved agent configuration at $state_file." >&2
    exit 1
  }
  exec lk --config "$state_file" agent status
fi

if [[ "$action" == create && -f "$state_file" ]]; then
  echo "Agent config already exists; use the deploy action instead." >&2
  exit 1
fi
if [[ "$action" == deploy && ! -f "$state_file" ]]; then
  echo "Agent config not found; first run the create action." >&2
  exit 1
fi

secret_file="${AQLYRA_VOICE_SECRETS_FILE:-}"
if [[ -z "$secret_file" || ! -f "$secret_file" || -L "$secret_file" ]]; then
  echo "Set AQLYRA_VOICE_SECRETS_FILE to an existing regular private .env file (not a symlink)." >&2
  exit 1
fi
secret_file="$(cd "$(dirname "$secret_file")" && pwd -P)/$(basename "$secret_file")"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "${script_dir}/../.." && pwd -P)"
backend_dir="${repo_root}/backend"

case "$secret_file" in
  "$repo_root"/*)
    echo "Keep voice.env outside the Git repository; it is sent to the LiveKit secrets store." >&2
    exit 1
    ;;
esac



secret_mode="$(stat -c '%a' "$secret_file" 2>/dev/null || stat -f '%Lp' "$secret_file" 2>/dev/null || true)"
if [[ ! "$secret_mode" =~ ^[0-7]{3,4}$ ]]; then
  echo "Could not verify private voice.env file permissions; set mode 600." >&2
  exit 1
fi
secret_mode_value=$((8#$secret_mode))
if (( (secret_mode_value & 077) != 0 )); then
  echo "voice.env is readable by group or other users; run chmod 600 on it." >&2
  exit 1
fi

# LiveKit injects these credentials for the selected cloud project.
# Prevent accidentally attaching secrets from a different LiveKit project.
if grep -Eq '^[[:space:]]*(LIVEKIT_URL|LIVEKIT_API_KEY|LIVEKIT_API_SECRET)=' "$secret_file"; then
  echo "Remove LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET from the secrets file." >&2
  exit 1
fi
for required in DATABASE_URL GROQ_API_KEY SECRET_KEY; do
  if ! grep -Eq "^[[:space:]]*${required}=[^[:space:]]+" "$secret_file"; then
    echo "Missing required setting: ${required} (no value printed)." >&2
    exit 1
  fi
done



for required_file in Dockerfile.voice requirements.txt requirements-voice.txt .dockerignore; do
  [[ -f "${backend_dir}/${required_file}" ]] || {
    echo "Missing backend file: ${required_file}" >&2
    exit 1
  }
done
[[ -d "${backend_dir}/app" ]] || {
  echo "Missing backend/app." >&2
  exit 1
}

# The API Dockerfile and voice Dockerfile have different roles.
# Package a temporary *voice-only* build context instead of modifying either.
context="$(mktemp -d)"
trap 'rm -rf "$context"' EXIT
cp "${backend_dir}/Dockerfile.voice" "${context}/Dockerfile"
cp "${backend_dir}/requirements.txt" "${backend_dir}/requirements-voice.txt" "$context/"
cp "${backend_dir}/.dockerignore" "$context/.dockerignore"
cp -R "${backend_dir}/app" "$context/app"

mkdir -p "$state_dir"
if [[ -L "$state_dir" || ! -d "$state_dir" ]]; then
  echo "LiveKit state directory must be a real directory, not a symlink." >&2
  exit 1
fi
chmod 700 "$state_dir"
if [[ "$action" == deploy ]]; then
  cp "$state_file" "$context/livekit.toml"
fi

if [[ "$action" == create ]]; then
  region_args=()
  if [[ -n "${AQLYRA_LIVEKIT_REGION:-}" ]]; then
    region_args=(--region "$AQLYRA_LIVEKIT_REGION")
  fi
  (
    cd "$context"
    lk agent create "${region_args[@]}" --secrets-file "$secret_file"
  )
  if [[ ! -f "$context/livekit.toml" ]]; then
    echo "LiveKit created no agent config. Check CLI output and agent list." >&2
    exit 1
  fi
  state_tmp="${state_file}.tmp.$"
  cp "$context/livekit.toml" "$state_tmp"
  chmod 600 "$state_tmp"
  mv "$state_tmp" "$state_file"
else
  (
    cd "$context"
    lk agent deploy --secrets-file "$secret_file"
  )
fi

echo "LiveKit Cloud agent operation completed. Checking status..."
lk --config "$state_file" agent status
