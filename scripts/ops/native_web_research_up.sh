#!/usr/bin/env bash
# Start ONLY the existing native, loopback-bound Aqlyra backend for Web Research.
# Reuses isolated PostgreSQL from the operator's existing native recovery.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="${HOME}/aqlyra-native-recovery"
PG="$(brew --prefix postgresql@16)/bin"

test -f "$BASE/postgres.password" || { echo "Missing existing native PostgreSQL config"; exit 1; }
test -f "$BASE/pgdata/PG_VERSION" || { echo "Missing native PostgreSQL cluster"; exit 1; }
test -f "$ROOT/backend/.env" || { echo "Missing private backend/.env"; exit 1; }
test -x "$ROOT/backend/.venv/bin/uvicorn" || { echo "Missing existing FastAPI venv"; exit 1; }
test -f "$ROOT/backend/app/services/web_research_service.py" || { echo "Update Git checkout to Web Research branch first"; exit 1; }
test -d "$BASE/uploads" || { echo "Existing uploaded documents not found"; exit 1; }
"$PG/pg_isready" -h 127.0.0.1 -p 55416 >/dev/null || {
  echo "Existing native PostgreSQL on port 55416 is offline"; exit 1;
}

export PGPASSWORD="$(cat "$BASE/postgres.password")"
export DATABASE_URL="postgresql+psycopg://$(id -un):${PGPASSWORD}@127.0.0.1:55416/aqlyra_recovery"
export UPLOAD_DIR="$BASE/uploads"
export WEB_RESEARCH_ENABLED=true
export TAVILY_KEYLESS_ENABLED=true
export RATE_LIMIT_ENABLED=false

REV="$("$PG/psql" -h 127.0.0.1 -p 55416 -U "$(id -un)" -d aqlyra_recovery -Atqc 'SELECT version_num FROM alembic_version')"
test "$REV" = "f18a3c42e917" || {
  echo "Unexpected Aqlyra schema revision; refusing to change DB"; exit 1;
}

cd "$ROOT/backend"
.venv/bin/python - <<'PY'
from app.config.settings import settings

if settings.is_production:
    raise SystemExit("Refusing production configuration for local keyless web research")
if settings.LLM_PROVIDER == "groq" and not settings.GROQ_API_KEY:
    raise SystemExit("Set GROQ_API_KEY privately in backend/.env")
if settings.LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
    raise SystemExit("Set OPENAI_API_KEY privately in backend/.env")
if settings.LLM_PROVIDER not in ("groq", "openai"):
    raise SystemExit("Set LLM_PROVIDER=groq or openai (not deterministic) in backend/.env")
if settings.LLM_PROVIDER == "groq" and settings.LLM_MODEL == "gpt-5":
    raise SystemExit("Configure a Groq-compatible LLM_MODEL in backend/.env")
print("Live LLM configured:", settings.LLM_PROVIDER)
print("Tavily:", "keyed" if settings.TAVILY_API_KEY else "keyless local mode")
PY

CURRENT="$(lsof -nP -tiTCP:8010 -sTCP:LISTEN || true)"
PID="$(cat "$BASE/fastapi.pid" 2>/dev/null || true)"
if [[ -n "$CURRENT" ]]; then
  if [[ "$CURRENT" != "$PID" ]]; then
    echo "Port 8010 is not the tracked native Aqlyra process; refusing to stop it."
    exit 1
  fi
  CMD="$(ps -p "$PID" -o command= || true)"
  if [[ "$CMD" != *"uvicorn app.main:app"* ]]; then
    echo "Tracked process is not Aqlyra uvicorn; refusing to stop it."
    exit 1
  fi
  kill "$PID"
  for i in $(seq 1 20); do
    lsof -nP -tiTCP:8010 -sTCP:LISTEN >/dev/null || break
    sleep 1
  done
fi

if lsof -nP -tiTCP:8010 -sTCP:LISTEN >/dev/null; then
  echo "Port 8010 still occupied; refusing to overwrite unrelated service."
  exit 1
fi

nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 \
  > "$BASE/fastapi.log" 2>&1 &
echo "$!" > "$BASE/fastapi.pid"

for i in $(seq 1 30); do
  if curl --silent --fail --max-time 3 \
    http://127.0.0.1:8010/api/v1/readiness > /dev/null; then
    echo "AQlyra Native Backend: READY"
    echo "Web research: http://127.0.0.1:3000/web"
    open "http://127.0.0.1:3000/web"
    exit 0
  fi
  sleep 1
done
echo "Backend startup error (no provider secrets should be shared):"
tail -n 25 "$BASE/fastapi.log"
exit 1
