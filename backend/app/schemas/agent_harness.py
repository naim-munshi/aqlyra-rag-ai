from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.rag import RAGAnswerResponse

AgentChunkRole = Literal["content", "summary", "proposition"]


class AgentResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)
    document_ids: list[str] = Field(default_factory=list, max_length=50)
    chunk_roles: list[AgentChunkRole] = Field(default_factory=lambda: ["content", "summary"], min_length=1)
    top_k: int = Field(default=8, ge=1, le=12)
    max_context_tokens: int = Field(default=2_400, ge=256, le=4_000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty")
        return cleaned

    @field_validator("document_ids")
    @classmethod
    def unique_document_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("Document IDs must be non-empty and unique")
        return cleaned

    @field_validator("chunk_roles")
    @classmethod
    def unique_chunk_roles(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Chunk roles must be unique")
        return values


class AgentTraceStepResponse(BaseModel):
    id: str
    step_index: int
    step_type: str
    tool_name: str | None
    status: str
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    latency_ms: int
    input_tokens: int
    output_tokens: int
    created_at: datetime


class AgentResearchResponse(RAGAnswerResponse):
    trace_id: str
    cost_usd: float
    cost_basis: str
    steps: list[AgentTraceStepResponse]


class AgentRunSummaryResponse(BaseModel):
    id: str
    trace_id: str
    question_redacted: str
    status: str
    provider_name: str | None
    model_name: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_basis: str
    latency_ms: int
    created_at: datetime


class AgentRunDetailResponse(AgentRunSummaryResponse):
    answer_redacted: str | None
    steps: list[AgentTraceStepResponse]


class AgentDailyUsageResponse(BaseModel):
    usage_date: date
    request_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class AgentUsageDashboardResponse(BaseModel):
    daily_budget_usd: float
    daily_usage: list[AgentDailyUsageResponse]
