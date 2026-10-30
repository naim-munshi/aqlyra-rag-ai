#!/bin/sh

set -eu

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
