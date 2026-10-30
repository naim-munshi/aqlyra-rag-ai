"""Fail-closed voice job authorization against current database state.

A LiveKit dispatch JWT is not a durable authorization grant: an account,
conversation, or document may have been deleted or revoked after the browser
received its 10-minute room token. Never trust just the metadata.
"""
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.user import User
from app.services.conversation_service import get_conversation_for_user
from app.services.document_service import get_user_document
from app.voice.job_metadata import VoiceJobData


class VoiceJobAuthorizationError(PermissionError):
    """Do not include private user identifiers in error messages."""


def authorize_voice_job(db: Session, job: VoiceJobData) -> None:
    user = db.get(User, job.user_id)
    if (
        user is None
        or not user.is_active
        or (
            settings.EMAIL_VERIFICATION_REQUIRED
            and user.email_verified_at is None
        )
    ):
        raise VoiceJobAuthorizationError("Voice identity is no longer authorized")

    conversation = get_conversation_for_user(
        db=db, user_id=job.user_id, conversation_id=job.conversation_id,
    )
    if conversation is None or conversation.mode != job.mode:
        raise VoiceJobAuthorizationError("Voice conversation is no longer available")

    for document_id in job.document_ids:
        document = get_user_document(
            db=db, user_id=job.user_id, document_id=document_id,
        )
        if document is None or document.status != "ready":
            raise VoiceJobAuthorizationError("Voice document scope is no longer available")
