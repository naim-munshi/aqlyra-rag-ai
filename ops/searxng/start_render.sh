#!/bin/sh
set -eu
if [ "${#SEARXNG_SECRET}" -lt 32 ] || [ "${#SEARXNG_SERVICE_TOKEN}" -lt 32 ]; then
  echo "Search service requires SEARXNG_SECRET and SEARXNG_SERVICE_TOKEN." >&2
  exit 64
fi
# Public access is ONLY via the separate token-protected gateway on $PORT.
export GRANIAN_HOST=127.0.0.1
export GRANIAN_PORT=8080
/usr/local/searxng/entrypoint.sh &
searx_pid=$!
trap 'kill "$searx_pid" 2>/dev/null || true' INT TERM EXIT
exec python3 /usr/local/bin/aqlyra-search-gateway.py
