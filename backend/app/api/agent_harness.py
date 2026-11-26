"""Authenticated Knowledge research-agent endpoints and owner-only trace viewer."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.core.rate_limit import limit_rag_request
from app.database.connection import get_db
from app.embeddings import EmbeddingError
from app.llms import LLMProviderRequestError
from app.models.agent_trace import AgentRun, AgentStep
from app.models.user import User
from app.schemas.agent_harness import (
    AgentDailyUsageResponse, AgentResearchRequest, AgentResearchResponse,
    AgentRunDetailResponse, AgentRunSummaryResponse, AgentTraceStepResponse,
    AgentUsageDashboardResponse,
)
from app.schemas.rag import RAGCitationResponse, RAGUsageResponse
from app.services.agent_harness_service import (
    AgentBudgetExceeded, AgentBudgetUnavailable, AgentInputRejected,
    get_agent_run, list_agent_daily_usage, list_agent_runs, redact_pii, run_research_agent,
)

router = APIRouter(prefix="/agent-harness", tags=["Agent Harness"])
PRIVATE_HEADERS = {"Cache-Control": "private, no-store, max-age=0", "Vary": "Cookie"}

def _require_agent_access(user: User) -> None:
    if not settings.AGENT_HARNESS_ENABLED:
        raise HTTPException(status_code=503, detail="Knowledge research agent is disabled.")

    allowed_user_ids = {
        item.strip()
        for item in settings.AGENT_HARNESS_ALLOWED_USER_IDS.split(",")
        if item.strip()
    }
    if not allowed_user_ids or str(user.id) not in allowed_user_ids:
        raise HTTPException(
            status_code=403,
            detail="Knowledge research agent is not enabled for this account.",
        )



def _step_response(step: AgentStep) -> AgentTraceStepResponse:
    return AgentTraceStepResponse(
        id=step.id, step_index=step.step_index, step_type=step.step_type,
        tool_name=step.tool_name, status=step.status,
        input_summary=step.input_summary or {}, output_summary=step.output_summary or {},
        latency_ms=step.latency_ms, input_tokens=step.input_tokens,
        output_tokens=step.output_tokens, created_at=step.created_at,
    )


def _run_summary(run: AgentRun) -> AgentRunSummaryResponse:
    return AgentRunSummaryResponse(
        id=run.id, trace_id=run.trace_id,
        question_redacted=run.question_redacted, status=run.status,
        provider_name=run.provider_name, model_name=run.model_name,
        input_tokens=run.input_tokens, output_tokens=run.output_tokens,
        cost_usd=float(run.cost_usd), cost_basis=run.cost_basis,
        latency_ms=run.latency_ms, created_at=run.created_at,
    )


@router.post(
    "/research", response_model=AgentResearchResponse,
    dependencies=[Depends(limit_rag_request)],
)
def research(
    request: AgentResearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentResearchResponse:
    _require_agent_access(user)
    try:
        result = run_research_agent(
            db=db, user_id=str(user.id), question=request.question,
            document_ids=tuple(request.document_ids),
            chunk_roles=tuple(request.chunk_roles),
            top_k=request.top_k, max_context_tokens=request.max_context_tokens,
        )
    except AgentInputRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AgentBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AgentBudgetUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EmbeddingError, LLMProviderRequestError) as exc:
        raise HTTPException(status_code=503, detail="Knowledge research provider is unavailable.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Knowledge research failed safely. No unverified answer was returned.") from exc

    answer = result.answer
    citations = [
        RAGCitationResponse(
            source_id=source.source_id, chunk_id=source.chunk_id,
            document_id=source.document_id, parent_chunk_id=source.parent_chunk_id,
            filename=source.original_filename, chunk_role=source.chunk_role,
            chunk_level=source.chunk_level, chunk_index=source.chunk_index,
            source_label=source.source_label, section_path=list(source.section_path),
            start_page=source.start_page, end_page=source.end_page,
            similarity_score=source.similarity_score, excerpt=redact_pii(source.content),
            was_truncated=source.was_truncated,
        )
        for source in answer.citations
    ]
    return AgentResearchResponse(
        question=answer.question, answer=result.answer_text,
        is_refusal=answer.is_refusal or not citations,
        provider_name=answer.provider_name, model_name=answer.model_name,
        response_id=answer.response_id, citations=citations,
        citation_count=len(citations), retrieved_count=answer.retrieved_count,
        context_source_count=answer.context_source_count,
        skipped_evidence_count=answer.skipped_evidence_count,
        evidence_was_truncated=answer.evidence_was_truncated,
        usage=RAGUsageResponse(
            input_tokens=answer.input_tokens, output_tokens=answer.output_tokens,
            total_tokens=answer.total_tokens, evidence_tokens=answer.evidence_tokens,
        ),
        trace_id=result.run.trace_id, cost_usd=float(result.cost_usd),
        cost_basis=result.cost_basis, steps=[_step_response(step) for step in result.steps],
    )


@router.get("/usage", response_model=AgentUsageDashboardResponse)
def usage_dashboard(
    response: Response,
    days: int = Query(default=14, ge=1, le=31),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentUsageDashboardResponse:
    if not settings.AGENT_HARNESS_ENABLED:
        raise HTTPException(status_code=503, detail="Knowledge research agent is disabled.")
    response.headers.update(PRIVATE_HEADERS)
    rows = list_agent_daily_usage(db, user_id=str(user.id), days=days)
    return AgentUsageDashboardResponse(
        daily_budget_usd=settings.AGENT_DAILY_BUDGET_USD,
        daily_usage=[
            AgentDailyUsageResponse(
                usage_date=row.usage_date,
                request_count=row.request_count,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                cost_usd=float(row.cost_usd),
            )
            for row in rows
        ],
    )


@router.get("/runs", response_model=list[AgentRunSummaryResponse])
def runs(
    response: Response,
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentRunSummaryResponse]:
    if not settings.AGENT_HARNESS_ENABLED:
        raise HTTPException(status_code=503, detail="Knowledge research agent is disabled.")
    response.headers.update(PRIVATE_HEADERS)
    return [_run_summary(run) for run in list_agent_runs(db, user_id=str(user.id), limit=limit)]


@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
def run_detail(
    run_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRunDetailResponse:
    if not settings.AGENT_HARNESS_ENABLED:
        raise HTTPException(status_code=503, detail="Knowledge research agent is disabled.")
    response.headers.update(PRIVATE_HEADERS)
    run = get_agent_run(db, user_id=str(user.id), run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent trace not found.")
    return AgentRunDetailResponse(
        **_run_summary(run).model_dump(),
        answer_redacted=run.answer_redacted,
        steps=[_step_response(step) for step in run.steps],
    )
