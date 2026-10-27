"""Privacy-preserving admin-only monitoring and aggregate account statistics."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.core.monitoring import admin_http_snapshot
from app.database.connection import get_db
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Admin"])


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Explicit immutable user-ID allowlist; disabled if not configured."""
    if user.id not in settings.ADMIN_USER_IDS.split(","):
        raise HTTPException(status_code=403, detail="Forbidden")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


@router.get("/overview")
def admin_overview(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    today = utc_now_naive().date()
    first_day = today - timedelta(days=6)
    start = utc_now_naive().replace(
        year=first_day.year, month=first_day.month, day=first_day.day,
        hour=0, minute=0, second=0, microsecond=0,
    )

    registered_total = db.scalar(select(func.count()).select_from(User)) or 0
    active_accounts = db.scalar(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    ) or 0
    verified_accounts = db.scalar(
        select(func.count()).select_from(User).where(
            User.email_verified_at.is_not(None)
        )
    ) or 0
    total_documents = db.scalar(select(func.count()).select_from(Document)) or 0
    total_conversations = db.scalar(select(func.count()).select_from(Conversation)) or 0

    registrations = db.execute(
        select(func.date(User.created_at), func.count())
        .where(User.created_at >= start)
        .group_by(func.date(User.created_at))
    ).all()
    daily_counts = {str(day): int(count) for day, count in registrations}
    signup_days = [
        {
            "date": (first_day + timedelta(days=day)).isoformat(),
            "count": daily_counts.get(
                (first_day + timedelta(days=day)).isoformat(), 0
            ),
        }
        for day in range(7)
    ]

    return JSONResponse(
        {
            "users": {
                "registered_total": int(registered_total),
                "active_accounts": int(active_accounts),
                "verified_accounts": int(verified_accounts),
                "documents_total": int(total_documents),
                "conversations_total": int(total_conversations),
                "signups_last_7_days": signup_days,
            },
            "traffic": admin_http_snapshot(),
            "generated_at": utc_now_naive().isoformat() + "Z",
        },
        headers={"Cache-Control": "no-store, private"},
    )
