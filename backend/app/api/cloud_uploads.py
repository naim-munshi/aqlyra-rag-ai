"""Opt-in, authenticated browser-to-private-storage upload handshake.

NO public upload routes are enabled without BOTH private storage and the
separate CLOUD_UPLOAD_PUBLIC_ENABLED launch gate. Do not enable prior to
cloud-aware delete, orphan cleanup, backup and live two-tenant acceptance.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from datetime import timedelta
from sqlalchemy import select
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.rate_limit import limit_upload_request
from app.database.connection import get_db
from app.models.user import User
from app.models.cloud_upload_intent import CloudUploadIntent
from app.core.datetime_utils import utc_now_naive
from app.schemas.document import DocumentResponse
from app.services.document_service import get_user_document
from app.services.cloud_document_finalization import (
    CloudFinalizationConflict,
    finalize_cloud_upload,
    recover_promoted_cloud_document,
)
from app.services.cloud_upload_intent_service import reserve_upload_intent
from app.services.private_object_storage import PrivateObjectStorageError
from app.services.cloud_proxy_upload import persist_small_private_cloud_upload
from app.services.storage_service import (
    EmptyFileError, FileTooLargeError, InvalidFileContentError,
    UnsupportedFileTypeError,
)


router = APIRouter(prefix="/documents/cloud", tags=["Cloud Uploads"])


class UploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=1, le=52428800)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _require_cloud_enabled() -> None:
    if not (
        settings.CLOUD_UPLOAD_PUBLIC_ENABLED
        and settings.PRIVATE_OBJECT_STORAGE_ENABLED
    ):
        raise HTTPException(status_code=404, detail="Cloud upload unavailable")


@router.post(
    "/prepare", status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_upload_request)],
)
def prepare_cloud_upload(
    payload: UploadIntentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_cloud_enabled()
    if not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verified account required for uploads")
    try:
        reserved = reserve_upload_intent(
            db=db, owner=user,
            original_filename=payload.filename,
            expected_size=payload.size_bytes,
            expected_sha256=payload.sha256,
        )
    except PrivateObjectStorageError as exc:
        raise HTTPException(status_code=400, detail="Invalid cloud upload") from exc
    return {
        "intent_id": reserved.intent_id,
        "expires_at": reserved.expires_at.isoformat() + "Z",
        "upload_url": reserved.grant.put_url,
        "method": "PUT",
        "headers": reserved.grant.headers,
        "expires_in_seconds": reserved.grant.expires_in_seconds,
    }


@router.post(
    "/{intent_id}/finalize",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentResponse,
    dependencies=[Depends(limit_upload_request)],
)
def finalize_cloud_upload_request(
    intent_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    _require_cloud_enabled()
    try:
        finalized = finalize_cloud_upload(
            db=db, owner=user, intent_id=intent_id,
        )
    except CloudFinalizationConflict as exc:
        raise HTTPException(
            status_code=409, detail="Cloud upload cannot be finalized"
        ) from exc
    except PrivateObjectStorageError as exc:
        raise HTTPException(
            status_code=409, detail="Cloud upload verification failed"
        ) from exc
    document = get_user_document(
        db=db, user_id=str(user.id), document_id=finalized.document_id,
    )
    if document is None:
        raise HTTPException(status_code=503, detail="Document unavailable")
    return DocumentResponse.model_validate(document)


@router.post(
    "/proxy", status_code=status.HTTP_201_CREATED,
    response_model=DocumentResponse,
    dependencies=[Depends(limit_upload_request)],
)
async def small_private_cloud_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    # Separate opt-in: no browser signed-URL route or CORS dependency.
    if not (
        settings.PRIVATE_OBJECT_STORAGE_ENABLED
        and settings.CLOUD_UPLOAD_PROXY_ENABLED
    ):
        raise HTTPException(status_code=503, detail="Private file upload unavailable")
    if not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verified account required for uploads")
    try:
        document = await persist_small_private_cloud_upload(
            upload=file, owner=user, db=db,
        )
        return DocumentResponse.model_validate(document)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (EmptyFileError, InvalidFileContentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CloudFinalizationConflict as exc:
        raise HTTPException(
            status_code=409, detail="Document already uploaded or cannot be finalized",
        ) from exc
    except PrivateObjectStorageError as exc:
        # Sanitized. Never expose provider endpoints, keys or grant URLs.
        raise HTTPException(
            status_code=503, detail="Secure document storage is temporarily unavailable",
        ) from exc


@router.post(
    "/recover",
    dependencies=[Depends(limit_upload_request)],
)
def recover_owner_pending_cloud_uploads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Attempt only the authenticated owner's claimed, stale private objects.

    Explicit action; never a global sweep or a blind S3 delete. A claimed
    object has a DB-reserved final key which can be reverified by SHA256.
    Skip recent claims to avoid interfering with an in-flight finalization.
    """
    if not (
        settings.PRIVATE_OBJECT_STORAGE_ENABLED
        and (settings.CLOUD_UPLOAD_PROXY_ENABLED or settings.CLOUD_UPLOAD_PUBLIC_ENABLED)
    ):
        raise HTTPException(
            status_code=503, detail="Private upload recovery unavailable",
        )
    if not user.is_active or user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verified account required")

    cutoff = utc_now_naive() - timedelta(seconds=60)
    owner_id = str(user.id)
    candidates = db.scalars(
        select(CloudUploadIntent.id)
        .where(
            CloudUploadIntent.user_id == owner_id,
            CloudUploadIntent.status == "claimed",
            CloudUploadIntent.document_id.is_(None),
            CloudUploadIntent.final_object_key.is_not(None),
            CloudUploadIntent.claimed_at < cutoff,
        )
        .order_by(CloudUploadIntent.claimed_at)
        .limit(5)
    ).all()
    # A failed recovery must not poison the DB session for later items.
    db.rollback()
    recovered = []
    failures = 0
    for intent_id in candidates:
        try:
            result = recover_promoted_cloud_document(
                db=db, owner=user, intent_id=intent_id,
            )
            document = get_user_document(
                db=db, user_id=owner_id, document_id=result.document_id,
            )
            if document is not None:
                recovered.append(DocumentResponse.model_validate(document))
            else:
                failures += 1
        except Exception:
            # No credentials, object key or provider errors are disclosed.
            # Existing claimed intent and final object remain for retry.
            db.rollback()
            failures += 1
    return {"recovered": recovered, "attempted": len(candidates), "failed": failures}
