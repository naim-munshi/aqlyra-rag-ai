"""Privacy-preserving admin-only monitoring and aggregate account statistics."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.auth.admin_access import is_admin_user
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.core.monitoring import admin_http_snapshot
from app.database.connection import get_db
from app.models.conversation import Conversation
from app.models.cloud_upload_intent import CloudUploadIntent
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.embedding_record import EmbeddingRecord
from app.embeddings.remote_semantic_provider import MODEL as SEMANTIC_MODEL
from app.services.retrieval_exclusions import permitted_retrieval_document
from app.models.message import Message
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Admin"])


def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Explicit immutable user-ID allowlist; disabled if not configured."""
    if not is_admin_user(user):
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


    # Activity means an authenticated user sent a message that persisted.
    # It is NOT a count of unique site visitors, open sessions, or guest users.
    now = utc_now_naive()
    rolling_day = now - timedelta(hours=24)
    rolling_week = now - timedelta(days=7)
    summary = db.execute(
        select(
            func.count(func.distinct(Conversation.user_id)).label("users_7d"),
            func.count(func.distinct(Conversation.user_id))
            .filter(Message.created_at >= rolling_day)
            .label("users_24h"),
            func.count(Message.id).label("messages_7d"),
            func.count(Message.id)
            .filter(Message.created_at >= rolling_day)
            .label("messages_24h"),
        )
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.role == "user", Message.created_at >= rolling_week)
    ).one()

    daily_activity = db.execute(
        select(
            func.date(Message.created_at).label("day"),
            func.count(func.distinct(Conversation.user_id)).label("users"),
            func.count(Message.id).label("messages"),
        )
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.role == "user", Message.created_at >= start)
        .group_by(func.date(Message.created_at))
    ).all()
    activity_by_day = {
        str(row.day): (int(row.users), int(row.messages))
        for row in daily_activity
    }
    chat_days = [
        {
            "date": (first_day + timedelta(days=offset)).isoformat(),
            "users": activity_by_day.get(
                (first_day + timedelta(days=offset)).isoformat(), (0, 0)
            )[0],
            "messages": activity_by_day.get(
                (first_day + timedelta(days=offset)).isoformat(), (0, 0)
            )[1],
        }
        for offset in range(7)
    ]

    # Aggregate storage lifecycle indicators only. No object keys, filenames
    # or tenant IDs are returned to browsers, even for administrators.
    stale_since = utc_now_naive() - timedelta(minutes=5)
    sweep_since = utc_now_naive() - timedelta(hours=24)
    claimed = db.scalar(
        select(func.count()).select_from(CloudUploadIntent).where(
            CloudUploadIntent.status == "claimed",
        )
    ) or 0
    stale_claimed = db.scalar(
        select(func.count()).select_from(CloudUploadIntent).where(
            CloudUploadIntent.status == "claimed",
            CloudUploadIntent.claimed_at < stale_since,
        )
    ) or 0
    staging_cleanup_candidates = db.scalar(
        select(func.count()).select_from(CloudUploadIntent).where(
            CloudUploadIntent.status.in_(("completed", "issued")),
            CloudUploadIntent.stage_deleted_at.is_(None),
            CloudUploadIntent.expires_at < sweep_since,
        )
    ) or 0
    failed_uploads = db.scalar(
        select(func.count()).select_from(CloudUploadIntent).where(
            CloudUploadIntent.status == "failed",
        )
    ) or 0

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
            "chat_activity": {
                "active_users_last_24h": int(summary.users_24h),
                "active_users_last_7d": int(summary.users_7d),
                "user_messages_last_24h": int(summary.messages_24h),
                "user_messages_last_7d": int(summary.messages_7d),
                "daily_last_7_utc_days": chat_days,
                "scope": "persisted_authenticated_user_messages",
            },
            "traffic": admin_http_snapshot(),
            "cloud_storage": {
                "claimed": int(claimed),
                "stale_claimed": int(stale_claimed),
                "cleanup_candidates": int(staging_cleanup_candidates),
                "failed_intents": int(failed_uploads),
                "scope": "database_aggregate",
            },
            "generated_at": utc_now_naive().isoformat() + "Z",
        },
        headers={"Cache-Control": "no-store, private"},
    )


@router.get("/rag-coverage")
def admin_rag_coverage(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Current-model vector coverage; aggregate counts only, no private content.

    A row is indexed only if provider, model, 384D dimension and the exact
    chunk content hash match. Historical/stale/other-model rows never inflate
    coverage. This route does not issue any embedding/provider requests.
    """
    eligible = (
        Document.status == "ready",
        permitted_retrieval_document(),
    )
    ready_documents = db.scalar(
        select(func.count(Document.id)).where(*eligible)
    ) or 0
    chunk_scope = (
        select(func.count(DocumentChunk.id))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*eligible)
    )
    total = int(db.scalar(chunk_scope) or 0)
    current_vector = (
        select(EmbeddingRecord.id)
        .where(
            EmbeddingRecord.chunk_id == DocumentChunk.id,
            EmbeddingRecord.provider_name == "remote_onnx",
            EmbeddingRecord.model_name == SEMANTIC_MODEL,
            EmbeddingRecord.dimension == 384,
            EmbeddingRecord.content_hash == DocumentChunk.content_hash,
        )
        .exists()
    )
    indexed = int(db.scalar(chunk_scope.where(current_vector)) or 0)
    missing = total - indexed
    return JSONResponse(
        {
            "semantic_index": {
                "ready_documents": int(ready_documents),
                "eligible_chunks": total,
                "indexed_chunks": indexed,
                "missing_or_stale_chunks": missing,
                "coverage_percent": round(indexed * 100.0 / total, 2) if total else None,
                "provider": "remote_onnx",
                "model": SEMANTIC_MODEL,
                "dimension": 384,
                "scope": "ready_nonquarantined_chunks_all_roles_aggregate",
            },
            "generated_at": utc_now_naive().isoformat() + "Z",
        },
        headers={"Cache-Control": "private, no-store", "Vary": "Cookie"},
    )
