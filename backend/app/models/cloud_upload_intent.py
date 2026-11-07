"""Persistent upload-intent states; a new table, no changes to existing RAG tables."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Index,
    String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base


class CloudUploadIntent(Base):
    __tablename__ = "cloud_upload_intents"

    __table_args__ = (
        CheckConstraint(
            "status IN ('issued', 'claimed', 'completed', 'failed')",
            name="ck_cloud_upload_intents_status",
        ),
        CheckConstraint(
            "expected_size > 0 AND expected_size <= 26214400",
            name="ck_cloud_upload_intents_size",
        ),
        UniqueConstraint("object_key", name="uq_cloud_upload_intents_object_key"),
        UniqueConstraint(
            "final_object_key", name="uq_cloud_upload_intents_final_object_key",
        ),
        UniqueConstraint("document_id", name="uq_cloud_upload_intents_document_id"),
        Index("ix_cloud_upload_intents_recovery", "status", "claimed_at"),
        Index("ix_cloud_upload_intents_stage_cleanup", "status", "expires_at"),
        Index(
            "ix_cloud_upload_intents_owner_status_expiry",
            "user_id", "status", "expires_at",
        ),
        Index("ix_cloud_upload_intents_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    object_key: Mapped[str] = mapped_column(String(250), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    expected_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="issued", server_default="issued",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now_naive,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Persisted before remote final-object upload for safe crash reconciliation.
    final_object_key: Mapped[str | None] = mapped_column(
        String(250), nullable=True,
    )
    # Set in the SAME database transaction that inserts Document.
    document_id: Mapped[str | None] = mapped_column(
        String(), ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Explicit user-initiated deletion; distinct from missing/corrupt links.
    # Stage bytes need a second sweep AFTER the signed upload grant expires.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    stage_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
