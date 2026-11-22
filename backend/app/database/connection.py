from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def connection_pool_kwargs() -> dict:
    """Bound SQLAlchemy connections, including for Neon pooled endpoints."""
    return {
        "pool_pre_ping": True,
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT_SECONDS,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE_SECONDS,
    }


engine = create_engine(
    settings.DATABASE_URL,
    **connection_pool_kwargs(),
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()