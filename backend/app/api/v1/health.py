import tempfile

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from sqlalchemy import text

from app.config.settings import settings
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

    try:
        db.execute(
            text("SELECT 1")
        )

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
        except RedisError:
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
