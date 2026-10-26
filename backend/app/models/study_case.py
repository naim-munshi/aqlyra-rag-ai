"""Private application journey; avoid storing passport numbers or financial values."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.datetime_utils import utc_now_naive
from app.database.base import Base
from app.study_abroad.workflows import initial_checklist

class StudyCase(Base):
    __tablename__ = "study_cases"
    __table_args__ = (Index("ix_study_cases_owner_updated", "user_id", "updated_at"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workflow: Mapped[str] = mapped_column(String(24), nullable=False, default="student")
    nationality: Mapped[str] = mapped_column(String(80), nullable=False)
    residence_country: Mapped[str] = mapped_column(String(80), nullable=False)
    destination_country: Mapped[str] = mapped_column(String(80), nullable=False)
    degree_level: Mapped[str] = mapped_column(String(80), nullable=False)
    study_field: Mapped[str] = mapped_column(String(120), nullable=False)
    intake: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="profile")
    checklist: Mapped[dict] = mapped_column(JSON, nullable=False, default=initial_checklist)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive)

class StudyCaseDocument(Base):
    __tablename__ = "study_case_documents"
    case_id: Mapped[str] = mapped_column(String, ForeignKey("study_cases.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    checklist_key: Mapped[str] = mapped_column(String(50), nullable=False)

class StudyResearchReport(Base):
    __tablename__ = "study_research_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("study_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, nullable=False)
    searched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)

class StudyUniversity(Base):
    """University wishlist; data manually curated by user, not verified by Aqlyra."""
    __tablename__ = "study_universities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("study_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    program: Mapped[str] = mapped_column(String(160), nullable=False)
    program_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    application_status: Mapped[str] = mapped_column(String(24), nullable=False, default="researching")
    deadline: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
