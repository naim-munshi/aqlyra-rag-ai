"""Verified operator-only account inventory and guarded account controls.

No public discovery. No user message/document content. Deactivation is
reversible; physical deletion is explicitly disabled by default and blocked
for any account with recorded uploads.
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin import get_current_admin
from app.auth.admin_access import is_admin_user, is_privileged_identity
from app.config.settings import settings
from app.database.connection import get_db
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/admin/users", tags=["Admin"])
audit_log = logging.getLogger("aqlyra.admin.user_actions")
private_headers = {"Cache-Control": "private, no-store, max-age=0"}


class AdminAccountStatusRequest(BaseModel):
    action: Literal["disable", "enable"]
    confirm_email: EmailStr


class AdminAccountDeleteRequest(BaseModel):
    confirm_email: EmailStr
    confirmation: Literal["DELETE ACCOUNT"]


def _protected_target(actor: User, target: User) -> None:
    if target.id == actor.id or is_privileged_identity(target):
        raise HTTPException(status_code=403, detail="Admin identities cannot be changed")


def _matching_email(target: User, email: str) -> None:
    if target.email.strip().lower() != email.strip().lower():
        raise HTTPException(status_code=409, detail="Account email confirmation mismatch")


def _safe_account_view(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_active": bool(user.is_active),
        "is_verified": user.email_verified_at is not None,
        "is_admin": is_admin_user(user),
        "created_at": user.created_at.isoformat() + "Z",
    }


@router.get("")
def list_accounts(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10000),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    # Server-bound filtering/paging avoids exposing the entire database at once.
    where = []
    search = q.strip().lower()
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append(User.email.ilike(f"%{escaped}%", escape="\\"))

    total = db.scalar(select(func.count()).select_from(User).where(*where)) or 0
    accounts = db.scalars(
        select(User).where(*where)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return JSONResponse(
        {
            "users": [_safe_account_view(user) for user in accounts],
            "total": int(total),
            "offset": offset,
            "limit": limit,
            "can_permanently_delete": bool(settings.ADMIN_ACCOUNT_DELETION_ENABLED),
        },
        headers=private_headers,
    )


@router.patch("/{user_id}/status")
def set_account_status(
    user_id: str,
    request: AdminAccountStatusRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    _protected_target(admin, target)
    _matching_email(target, str(request.confirm_email))

    desired = request.action == "enable"
    if target.is_active != desired:
        target.is_active = desired
        # Expire ALL older access and refresh tokens after a status change.
        target.auth_epoch += 1
        db.commit()
        db.refresh(target)
        audit_log.warning("admin_account_status_changed actor=%s target=%s active=%s",
                          admin.id, target.id, target.is_active)
    return JSONResponse({"user": _safe_account_view(target)}, headers=private_headers)


@router.delete("/{user_id}")
def delete_inactive_account(
    user_id: str,
    request: AdminAccountDeleteRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if not settings.ADMIN_ACCOUNT_DELETION_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Permanent deletion disabled pending storage/recovery acceptance",
        )
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    _protected_target(admin, target)
    _matching_email(target, str(request.confirm_email))
    if target.is_active:
        raise HTTPException(status_code=409, detail="Disable account before deletion")

    # Never orphan uploaded object-storage bytes or local files by SQL cascade.
    has_docs = db.scalar(
        select(Document.id).where(Document.user_id == target.id).limit(1)
    )
    has_uploads = db.scalar(
        select(CloudUploadIntent.id).where(
            CloudUploadIntent.user_id == target.id
        ).limit(1)
    )
    if has_docs is not None or has_uploads is not None:
        raise HTTPException(
            status_code=409,
            detail="Account has uploaded data; deletion requires verified storage cleanup",
        )

    actor_id, target_id = admin.id, target.id
    try:
        db.delete(target)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account has related records that prevent safe deletion",
        ) from exc
    audit_log.warning("admin_account_deleted actor=%s target=%s", actor_id, target_id)
    return JSONResponse({"deleted": True}, headers=private_headers)
