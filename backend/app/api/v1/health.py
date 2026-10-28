import tempfile

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from sqlalchemy import text

from app.config.settings import settings
from app.core.logging import app_logger
from app.database.connection import SessionLocal

from fastapi.responses import Response
from redis.exceptions import RedisError

from app.core.monitoring import render_prometheus_metrics
from app.core.rate_limit import get_rate_limit_redis


router = APIRouter()


@router.get("/health")
async def health():
    """
    Lightweight liveness check.

    This endpoint confirms that the API process
    is running. Dependency checks belong to
    /readiness.
    """
    return {
        "status": "healthy",
        "service": "aqlyra-rag-ai",
        "version": settings.VERSION,
    }


@router.get("/readiness")
def readiness():
    """
    Deployment readiness check.

    Confirms that PostgreSQL is reachable and the
    persistent upload storage is available and
    writable.
    """
    db = SessionLocal()
    check_stage = "database_connection"

    try:
        db.execute(
            text("SELECT 1")
        )

        # SELECT 1 succeeds on an empty Neon database. In production,
        # block RAG and accounts until the exact reviewed schema and
        # pgvector core dependencies have actually been migrated.
        if settings.is_production:
            check_stage = "schema_revision"
            version = db.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one_or_none()
            # The owner-approved Full schema is an additive successor to
            # the Core schema. A Core-only process must remain usable
            # during the protected Full Release cutover window, without
            # claiming that any Study Abroad routes are deployed.
            if version not in ("b5e4a019dc72", "d4ec2f9b7860"):
                raise RuntimeError("Aqlyra database revision is not current")
            if version == "d4ec2f9b7860":
                check_stage = "schema_full_additive"
                full_tables_ready = db.execute(
                    text(
                        "SELECT "
                        "to_regclass('public.study_cases') IS NOT NULL "
                        "AND to_regclass('public.study_case_documents') IS NOT NULL "
                        "AND to_regclass('public.study_research_reports') IS NOT NULL "
                        "AND to_regclass('public.study_universities') IS NOT NULL"
                    )
                ).scalar_one()
                if not full_tables_ready:
                    raise RuntimeError("Aqlyra additive schema tables are unavailable")

            check_stage = "schema_core"
            core_schema_ready = db.execute(
                text(
                    "SELECT "
                    "to_regclass('public.users') IS NOT NULL "
                    "AND to_regclass('public.documents') IS NOT NULL "
                    "AND EXISTS ("
                    "  SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                    ")"
                )
            ).scalar_one()
            if not core_schema_ready:
                raise RuntimeError("Aqlyra core schema/pgvector is unavailable")

        check_stage = "upload_storage"
        upload_dir = (
            settings
            .UPLOAD_DIR
            .expanduser()
            .resolve()
        )

        if (
            not upload_dir.exists()
            or not upload_dir.is_dir()
        ):
            raise RuntimeError(
                "Upload storage is unavailable"
            )

        with tempfile.NamedTemporaryFile(
            dir=upload_dir,
            prefix=".aqlyra-readiness-",
            delete=True,
        ):
            pass

    except Exception as exc:
        # Only fixed stage labels and exception class are emitted. Never
        # log the database URL, SQL exception text or user data.
        app_logger.warning(
            "readiness_backend_not_ready",
            stage=check_stage,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Service is not ready",
        ) from exc

    finally:
        db.close()

    if settings.RATE_LIMIT_ENABLED:
        try:
            redis_ready = bool(
                get_rate_limit_redis().ping()
            )
        except (RedisError, ValueError) as exc:
            # Log only the exception CLASS. Exception messages may expose
            # hostnames, usernames or other connection information.
            app_logger.warning(
                "readiness_redis_backend_unavailable",
                error_type=type(exc).__name__,
            )
            redis_ready = False

        if not redis_ready:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Service dependencies "
                    "are unavailable"
                ),
            )

    return {
        "status": "ready",
        "service": "aqlyra-rag-ai",
        "version": settings.VERSION,
        "checks": {
            "database": "ready",
            "storage": "ready",
            **({"redis": "ready"} if settings.RATE_LIMIT_ENABLED else {}),
        },
    }


@router.get(
    "/metrics",
    include_in_schema=False,
)
def metrics():
    return Response(
        content=render_prometheus_metrics(),
        media_type=(
            "text/plain; "
            "version=0.0.4; "
            "charset=utf-8"
        ),
        headers={
            "Cache-Control": "no-store",
        },
    )
