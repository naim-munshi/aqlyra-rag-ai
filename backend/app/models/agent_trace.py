"""Private, owner-scoped audit records for the bounded Knowledge research agent."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String,
    Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utc_now_naive
from app.database.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_user_created", "user_id", "created_at"),
        Index("ix_agent_runs_trace_id", "trace_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    answer_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    provider_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False, default=Decimal("0"))
    cost_basis: Mapped[str] = mapped_column(String(40), nullable=False, default="measured_generation_tokens")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guardrail_status: Mapped[str] = mapped_column(String(20), nullable=False, default="passed")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
        passive_deletes=True, order_by="AgentStep.step_index",
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_agent_steps_run_index"),
        Index("ix_agent_steps_run_index", "run_id", "step_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
    run: Mapped["AgentRun"] = relationship(back_populates="steps")


class AgentDailyUsage(Base):
    __tablename__ = "agent_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_agent_daily_usage_user_date"),
        Index("ix_agent_daily_usage_date", "usage_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive)
