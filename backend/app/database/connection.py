from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

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
# Staged tenant-scoped DB access is opt-in until all production prerequisites
# are verified. A regular Neon owner role has BYPASSRLS and is NOT protected
# by an RLS policy. SET LOCAL ROLE changes the current effective role only
# for the signed-in transaction. Backend admin/queue work remains privileged
# until a separate low-privilege DATABASE_URL is rolled out.
_TENANT_ROLE = "aqlyra_tenant_runtime"
_TENANT_INFO_KEY = "aqlyra_tenant_user_id"
_ADMIN_INFO_KEY = "aqlyra_rls_verified_admin"


def bind_authenticated_tenant(session: Session, user_id: str) -> None:
    """Bind a verified JWT subject before any tenant DB operation."""
    if not settings.TENANT_RLS_ENABLED:
        return
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("Tenant identity must be nonempty")
    existing = session.info.get(_TENANT_INFO_KEY)
    if existing == user_id:
        return
    # Never let a session switch to another user after SQL has run.
    if existing is not None or session.in_transaction():
        raise RuntimeError("Tenant must be bound before opening a transaction")
    session.info[_TENANT_INFO_KEY] = user_id


@event.listens_for(Session, "after_begin")
def _install_scoped_tenant_role(
    session: Session, transaction, connection,
) -> None:
    """SET LOCAL is safe for transaction-pooled Neon and reapplies on commit."""
    if not settings.TENANT_RLS_ENABLED:
        return
    user_id = session.info.get(_TENANT_INFO_KEY)
    if user_id is None or session.info.get(_ADMIN_INFO_KEY):
        return
    # No dynamic SQL identifiers. Fail closed on missing/grantless role.
    connection.exec_driver_sql("SET LOCAL ROLE aqlyra_tenant_runtime")
    connection.execute(
        text("SELECT set_config('aqlyra.tenant_user_id', :id, true)"),
        {"id": user_id},
    )


def permit_verified_admin_scope(session: Session) -> None:
    """Only call after the existing admin-user allowlist has passed."""
    if not settings.TENANT_RLS_ENABLED:
        return
    if not session.info.get(_TENANT_INFO_KEY):
        raise RuntimeError("Admin override requires verified user identity")
    session.info[_ADMIN_INFO_KEY] = True
    if session.in_transaction():
        # Reset to the original DB role only for this verified admin request.
        session.connection().exec_driver_sql("RESET ROLE")
