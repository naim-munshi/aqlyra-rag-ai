"""Opt-in, authenticated browser-to-private-storage upload handshake.

NO public upload routes are enabled without BOTH private storage and the
separate CLOUD_UPLOAD_PUBLIC_ENABLED launch gate. Do not enable prior to
cloud-aware delete, orphan cleanup, backup and live two-tenant acceptance.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.rate_limit import limit_upload_request
from app.database.connection import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import get_user_document
from app.services.cloud_document_finalization import (
    CloudFinalizationConflict,
    finalize_cloud_upload,
)
from app.services.cloud_upload_intent_service import reserve_upload_intent
from app.services.private_object_storage import PrivateObjectStorageError

router = APIRouter(prefix="/documents/cloud", tags=["Cloud Uploads"])


class UploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=1, le=26214400)
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
