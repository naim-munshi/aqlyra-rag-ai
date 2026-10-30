#!/bin/sh

set -eu

# Explicit one-boot synthetic S3 storage probe, OFF by default.
# Results are PRIVATE_S3_PROBE=PASS/FAIL in server logs; no user objects touched.
# Even PASS does NOT authorize turning on public uploads or artifact generation.
if [ "${AQLYRA_PRIVATE_STORAGE_PROBE_ON_BOOT:-false}" = "true" ]; then
  if python -m app.services.private_storage_probe; then
    :
  else
    echo "Private S3 probe failed; keep private file features disabled." >&2
  fi
fi

# Explicit, one-time CORS setup for authenticated, presigned browser PUT.
# Preserves all pre-existing bucket CORS rules; no document object touched.
# A failure is reported but cannot overwrite or delete existing user data.
if [ "${AQLYRA_PRIVATE_STORAGE_CORS_SETUP_ON_BOOT:-false}" = "true" ]; then
  if python -m app.services.private_cors_setup; then
    :
  else
    echo "Private S3 CORS setup failed; keep direct browser upload disabled." >&2
  fi
fi

# Optional synthetic 2x2 image -> REAL Groq vision model check.
# Do not pass user images or persist generated output.
if [ "${AQLYRA_VISION_PROBE_ON_BOOT:-false}" = "true" ]; then
  if python -m app.services.vision_provider_probe; then
    :
  else
    echo "Vision model provider check failed; investigate model access." >&2
  fi
fi

# One-time provider-backed Knowledge smoke, with NO user document reads.
if [ "${AQLYRA_KNOWLEDGE_PROVIDER_PROBE_ON_BOOT:-false}" = "true" ]; then
  if python -m app.services.knowledge_provider_probe; then
    :
  else
    echo "Knowledge provider check failed; inspect sanitized readiness logs." >&2
  fi
fi

# Free external staging uses a separate, explicitly reviewed schema migration
# step. Never perform CREATE EXTENSION or Alembic writes on container boot.
# Default remains 'auto' for existing local/Docker-compose workflows.
case "${DATABASE_MIGRATION_MODE:-auto}" in
  manual)
    echo "Database migrations intentionally disabled at startup."
    exec "$@"
    ;;
  auto)
    ;;
  *)
    echo "Invalid DATABASE_MIGRATION_MODE; expected auto or manual" >&2
    exit 1
    ;;
esac

echo "Waiting for PostgreSQL and preparing pgvector..."

python - <<'PY'
import time

from sqlalchemy import create_engine, text

from app.config.settings import settings


max_attempts = 30

for attempt in range(1, max_attempts + 1):
    engine = None

    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            isolation_level="AUTOCOMMIT",
        )

        with engine.connect() as connection:
            connection.execute(
                text(
                    "CREATE EXTENSION "
                    "IF NOT EXISTS vector"
                )
            )

        print(
            "PostgreSQL connection ready; "
            "pgvector extension available."
        )

        break

    except Exception as exc:
        if attempt == max_attempts:
            raise RuntimeError(
                "PostgreSQL did not become ready"
            ) from exc

        print(
            "PostgreSQL is not ready "
            f"(attempt {attempt}/{max_attempts})."
        )

        time.sleep(2)

    finally:
        if engine is not None:
            engine.dispose()
PY

echo "Applying Alembic migrations..."

alembic upgrade head

echo "Starting backend..."

exec "$@"
