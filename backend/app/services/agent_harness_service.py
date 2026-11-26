"""Bounded Knowledge research agent with privacy guardrails, tracing and budget controls."""
from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.core.rate_limit import get_rate_limit_redis
from app.llms import create_configured_llm_provider
from app.models.agent_trace import AgentDailyUsage, AgentRun, AgentStep
from app.retrieval import RetrievalQuery
from app.services.rag_answer_service import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    RAGAnswerResult,
    _retrieve_rag_hits,
    answer_question,
)

logger = logging.getLogger(__name__)

_EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
_INJECTION_PATTERNS = (
    re.compile(r"(?i)\b(ignore|disregard|override)\b.{0,60}\b(previous|prior|system|developer)\b.{0,30}\b(instruction|prompt|rule)s?\b"),
    re.compile(r"(?i)\b(reveal|print|show|dump)\b.{0,50}\b(system prompt|hidden prompt|api key|secret|environment variables?)\b"),
    re.compile(r"(?i)\b(bypass|disable)\b.{0,35}\b(guardrail|safety|security|access control)s?\b"),
)
_BUDGET_RESERVE_LUA = """
local current = tonumber(redis.call("GET", KEYS[1]) or "0")
local reserve = tonumber(ARGV[1])
local budget = tonumber(ARGV[2])
if current + reserve > budget then
  return 0
end
redis.call("SET", KEYS[1], tostring(current + reserve), "EX", tonumber(ARGV[3]))
return 1
""".strip()
_BUDGET_SETTLE_LUA = """
local current = tonumber(redis.call("GET", KEYS[1]) or "0")
local next_value = current + tonumber(ARGV[1])
if next_value < 0 then next_value = 0 end
redis.call("SET", KEYS[1], tostring(next_value), "EX", tonumber(ARGV[2]))
return tostring(next_value)
""".strip()


class AgentInputRejected(ValueError):
    """Input guardrail rejected the request."""


class AgentBudgetExceeded(RuntimeError):
    """User's UTC-day research budget is exhausted."""


class AgentBudgetUnavailable(RuntimeError):
    """Pricing or Redis budget enforcement is unavailable."""


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    run: AgentRun
    steps: tuple[AgentStep, ...]
    answer: RAGAnswerResult
    answer_text: str
    cost_usd: Decimal
    cost_basis: str


def redact_pii(value: str) -> str:
    """Mask common contact identifiers before model use and trace persistence."""
    value = _EMAIL_PATTERN.sub("[EMAIL]", value)
    return _PHONE_PATTERN.sub("[PHONE]", value)


def validate_agent_input(question: str) -> str:
    cleaned = question.strip()
    if not cleaned or len(cleaned) > 2_000:
        raise AgentInputRejected("Question must contain 1–2,000 characters.")
    if any(pattern.search(cleaned) for pattern in _INJECTION_PATTERNS):
        raise AgentInputRejected("This request contains instructions that the research agent will not execute.")
    return redact_pii(cleaned)


def build_research_plan(question: str, max_queries: int = 3) -> tuple[str, ...]:
    """Create a deterministic, bounded plan; the agent never invents tool names."""
    if not 1 <= max_queries <= 3:
        raise ValueError("max_queries must be between 1 and 3")
    clauses = [
        part.strip(" \t-•")
        for part in re.split(r"(?<=[?？.!。！？])\s+|\n+|\s+(?:and|also|এবং|そして)\s+", question, flags=re.IGNORECASE)
        if part.strip(" \t-•")
    ]
    candidates = [question.strip(), *clauses]
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.casefold()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(candidate[:500])
        if len(result) >= max_queries:
            break
    return tuple(result or [question[:500]])


def _budget_key(user_id: str, usage_date: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return f"aqlyra:agent-harness:budget:{digest}:{usage_date}"


def _pricing() -> tuple[Decimal, Decimal]:
    input_rate = settings.AGENT_INPUT_PRICE_PER_1M_USD
    output_rate = settings.AGENT_OUTPUT_PRICE_PER_1M_USD
    if input_rate is None or output_rate is None:
        raise AgentBudgetUnavailable("Model input/output prices must be configured before enabling the research agent.")
    return Decimal(str(input_rate)), Decimal(str(output_rate))


def _maximum_reservation(input_rate: Decimal, output_rate: Decimal) -> Decimal:
    input_cap = Decimal(settings.AGENT_MAX_INPUT_TOKENS)
    output_cap = Decimal(settings.AGENT_MAX_OUTPUT_TOKENS)
    reserve = (
        input_cap * input_rate + output_cap * output_rate
    ) / Decimal(1_000_000)
    return reserve.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _reserve_daily_budget(user_id: str, reserve: Decimal) -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    usage_date = now.date().isoformat()
    key = _budget_key(user_id, usage_date)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime_time.min, tzinfo=timezone.utc)
    ttl = max(60, int((midnight - now).total_seconds()) + 3600)
    try:
        allowed = get_rate_limit_redis().eval(
            _BUDGET_RESERVE_LUA, 1, key, str(reserve),
            str(settings.AGENT_DAILY_BUDGET_USD), ttl,
        )
    except (RedisError, ValueError) as exc:
        raise AgentBudgetUnavailable("Daily budget service is unavailable.") from exc
    if int(allowed or 0) != 1:
        raise AgentBudgetExceeded("Your daily research-agent budget has been reached.")
    return key, usage_date, ttl


def _settle_daily_budget(key: str, ttl: int, delta: Decimal) -> None:
    try:
        get_rate_limit_redis().eval(
            _BUDGET_SETTLE_LUA, 1, key, str(delta), ttl,
        )
    except (RedisError, ValueError):
        # The reservation is deliberately left in place until its TTL expires.
        # This is conservative: a telemetry outage cannot create free budget.
        logger.warning("agent_budget_reconcile_failed")


def _record_daily_usage(
    db: Session, *, user_id: str, usage_date: str,
    input_tokens: int, output_tokens: int, cost: Decimal,
) -> None:
    from datetime import date

    now = utc_now_naive()
    statement = pg_insert(AgentDailyUsage).values(
        id=str(uuid.uuid4()),
        user_id=user_id,
        usage_date=date.fromisoformat(usage_date),
        request_count=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        updated_at=now,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_agent_daily_usage_user_date",
        set_={
            "request_count": AgentDailyUsage.request_count + 1,
            "input_tokens": AgentDailyUsage.input_tokens + input_tokens,
            "output_tokens": AgentDailyUsage.output_tokens + output_tokens,
            "cost_usd": AgentDailyUsage.cost_usd + cost,
            "updated_at": now,
        },
    )
    db.execute(statement)


def _step(
    *, run_id: str, index: int, step_type: str, input_summary: dict[str, Any],
    output_summary: dict[str, Any], latency_ms: int, tool_name: str | None = None,
    status: str = "completed",
) -> AgentStep:
    return AgentStep(
        run_id=run_id, step_index=index, step_type=step_type,
        tool_name=tool_name, status=status,
        input_summary=input_summary, output_summary=output_summary,
        latency_ms=max(0, int(latency_ms)),
    )


def run_research_agent(
    *, db: Session, user_id: str, question: str,
    document_ids: tuple[str, ...] = (), chunk_roles: tuple[str, ...] = ("content", "summary"),
    top_k: int = 8, max_context_tokens: int = 2_400,
) -> AgentExecutionResult:
    if not settings.AGENT_HARNESS_ENABLED:
        raise AgentBudgetUnavailable("The research agent is not enabled.")
    safe_question = validate_agent_input(question)
    input_rate, output_rate = _pricing()
    reserve = _maximum_reservation(input_rate, output_rate)
    if reserve > Decimal(str(settings.AGENT_DAILY_BUDGET_USD)):
        raise AgentBudgetUnavailable("Configured per-run maximum exceeds the daily budget.")
    budget_key, usage_date, budget_ttl = _reserve_daily_budget(user_id, reserve)

    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    created = utc_now_naive()
    run = AgentRun(
        id=run_id, trace_id=trace_id, user_id=user_id,
        question_redacted=safe_question, status="running",
        metadata_json={
            "tool_allowlist": ["knowledge.search_documents"],
            "max_retrieval_steps": min(settings.AGENT_MAX_RETRIEVALS, settings.AGENT_MAX_STEPS - 4),
            "cost_scope": "llm_generation_tokens_only; embeddings and verifier internals are not itemized",
        },
        created_at=created,
    )
    steps: list[AgentStep] = []
    budget_settled = False

    try:
        db.add(run)
        db.flush()
        guardrail_started = time.perf_counter()
        steps.append(_step(
            run_id=run_id, index=0, step_type="input_guardrail",
            input_summary={"question_chars": len(safe_question), "document_scope_count": len(document_ids)},
            output_summary={"accepted": True, "pii_masked": safe_question != question.strip()},
            latency_ms=(time.perf_counter() - guardrail_started) * 1000,
        ))

        plan_started = time.perf_counter()
        allowed_retrievals = min(settings.AGENT_MAX_RETRIEVALS, settings.AGENT_MAX_STEPS - 4)
        queries = build_research_plan(safe_question, allowed_retrievals)
        steps.append(_step(
            run_id=run_id, index=1, step_type="plan",
            input_summary={"goal": safe_question},
            output_summary={"queries": list(queries), "max_steps": settings.AGENT_MAX_STEPS},
            latency_ms=(time.perf_counter() - plan_started) * 1000,
        ))

        provider = create_configured_llm_provider()
        retrieved_by_id: dict[str, Any] = {}
        retrieval_summaries: list[dict[str, Any]] = []
        for offset, query_text in enumerate(queries):
            if offset + 2 >= settings.AGENT_MAX_STEPS:
                break
            retrieval_started = time.perf_counter()
            hits = _retrieve_rag_hits(
                db=db,
                query=RetrievalQuery(
                    user_id=user_id, text=query_text, top_k=min(top_k, 6),
                    document_ids=document_ids, chunk_roles=chunk_roles,
                ),
            )
            for hit in hits:
                current = retrieved_by_id.get(hit.chunk_id)
                if current is None:
                    retrieved_by_id[hit.chunk_id] = hit
            latency = (time.perf_counter() - retrieval_started) * 1000
            retrieval_summaries.append({
                "query": query_text,
                "hit_count": len(hits),
                "chunk_ids": [hit.chunk_id for hit in hits[:8]],
            })
            steps.append(_step(
                run_id=run_id, index=len(steps), step_type="tool_call",
                tool_name="knowledge.search_documents",
                input_summary={"query": query_text, "top_k": min(top_k, 6), "document_scope_count": len(document_ids)},
                output_summary={"hit_count": len(hits), "chunk_ids": [hit.chunk_id for hit in hits[:8]]},
                latency_ms=latency,
            ))

        combined_hits = list(retrieved_by_id.values())
        if combined_hits:
            combined_hits.sort(
                key=lambda item: (
                    item.ranking_score if item.ranking_score is not None
                    else item.similarity_score
                ),
                reverse=True,
            )
        combined_hits = combined_hits[: min(24, max(top_k, top_k * 2))]

        synthesis_started = time.perf_counter()
        answer = answer_question(
            db=db, user_id=user_id, question=safe_question,
            retrieval_question=safe_question, top_k=top_k,
            document_ids=document_ids, chunk_roles=chunk_roles,
            max_context_tokens=max_context_tokens,
            max_source_tokens=min(700, max_context_tokens),
            max_sources=8, provider=provider,
            precomputed_hits=combined_hits,
        )
        synthesis_latency = (time.perf_counter() - synthesis_started) * 1000
        steps.append(_step(
            run_id=run_id, index=len(steps), step_type="reason_and_cite",
            input_summary={"retrieved_chunk_count": len(combined_hits)},
            output_summary={
                "citation_count": answer.citation_count,
                "is_refusal": answer.is_refusal,
                "citation_chunk_ids": [source.chunk_id for source in answer.citations],
            },
            latency_ms=synthesis_latency,
            status="refused" if answer.is_refusal else "completed",
        ))

        # Final citation gate is fail-closed. The core RAG service already
        # validates citations and grounding; this is an additional agent boundary.
        answer_text = answer.answer_text
        output_guardrail_passed = bool(answer.is_refusal or answer.citations)
        if not output_guardrail_passed:
            answer_text = INSUFFICIENT_EVIDENCE_MESSAGE
        answer_text = redact_pii(answer_text)
        steps.append(_step(
            run_id=run_id, index=len(steps), step_type="output_guardrail",
            input_summary={"citation_count": answer.citation_count},
            output_summary={
                "passed": output_guardrail_passed,
                "abstained": bool(answer.is_refusal or not answer.citations),
                "pii_masked": answer_text != answer.answer_text,
            },
            latency_ms=0,
            status="completed" if output_guardrail_passed else "abstained",
        ))

        input_tokens = int(answer.input_tokens or 0)
        output_tokens = int(answer.output_tokens or 0)
        usage_reported = answer.input_tokens is not None or answer.output_tokens is not None
        if answer.is_refusal and not usage_reported:
            actual_cost = Decimal("0")
            cost_basis = "no_generation"
        elif usage_reported:
            actual_cost = (
                Decimal(input_tokens) * input_rate
                + Decimal(output_tokens) * output_rate
            ) / Decimal(1_000_000)
            cost_basis = "measured_generation_tokens"
        else:
            # Conservative ceiling when the configured provider omits usage.
            actual_cost = reserve
            cost_basis = "upper_bound_usage_unavailable"
        actual_cost = actual_cost.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

        run.status = "refused" if answer.is_refusal or not answer.citations else "completed"
        run.answer_redacted = answer_text
        run.provider_name = answer.provider_name
        run.model_name = answer.model_name
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.cost_usd = actual_cost
        run.cost_basis = cost_basis
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        run.guardrail_status = "passed" if output_guardrail_passed else "abstained"
        run.metadata_json = {
            **(run.metadata_json or {}),
            "query_count": len(queries),
            "retrieval_count": len(retrieval_summaries),
            "unique_chunks": len(combined_hits),
            "price_input_per_1m_usd": str(input_rate),
            "price_output_per_1m_usd": str(output_rate),
            "budget_reservation_usd": str(reserve),
        }
        run.completed_at = utc_now_naive()
        db.add_all(steps)
        _record_daily_usage(
            db, user_id=user_id, usage_date=usage_date,
            input_tokens=input_tokens, output_tokens=output_tokens, cost=actual_cost,
        )
        db.commit()
        # Usage is now durable. A subsequent refresh/telemetry failure must
        # never release the reservation and allow the same spend twice.
        budget_settled = True
        db.refresh(run)
        _settle_daily_budget(budget_key, budget_ttl, actual_cost - reserve)
        return AgentExecutionResult(
            run=run, steps=tuple(steps), answer=answer,
            answer_text=answer_text, cost_usd=actual_cost, cost_basis=cost_basis,
        )
    except Exception as exc:
        db.rollback()
        try:
            failed = db.get(AgentRun, run_id)
            if failed is None:
                # Preserve a redacted failed trace even when execution failed
                # before its first commit (for example, during DB flush).
                run.status = "failed"
                run.guardrail_status = "failed"
                run.metadata_json = {
                    **(run.metadata_json or {}),
                    "error_type": type(exc).__name__,
                }
                run.latency_ms = int((time.perf_counter() - started) * 1000)
                run.completed_at = utc_now_naive()
                db.add(run)
                db.add_all(steps)
            else:
                failed.status = "failed"
                failed.guardrail_status = "failed"
                failed.metadata_json = {
                    **(failed.metadata_json or {}),
                    "error_type": type(exc).__name__,
                }
                failed.latency_ms = int((time.perf_counter() - started) * 1000)
                failed.completed_at = utc_now_naive()
            db.commit()
        except Exception:
            db.rollback()
        if not budget_settled:
            _settle_daily_budget(budget_key, budget_ttl, -reserve)
        raise


def list_agent_daily_usage(
    db: Session, *, user_id: str, days: int = 14,
) -> list[AgentDailyUsage]:
    """Return only this user's recent UTC-day aggregate usage rows."""
    bounded_days = max(1, min(days, 31))
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=bounded_days - 1)
    return list(db.scalars(
        select(AgentDailyUsage)
        .where(
            AgentDailyUsage.user_id == user_id,
            AgentDailyUsage.usage_date >= cutoff,
        )
        .order_by(AgentDailyUsage.usage_date.desc())
        .limit(bounded_days)
    ).all())


def list_agent_runs(db: Session, *, user_id: str, limit: int = 20) -> list[AgentRun]:
    return list(db.scalars(
        select(AgentRun).where(AgentRun.user_id == user_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(limit)
    ).all())


def get_agent_run(db: Session, *, user_id: str, run_id: str) -> AgentRun | None:
    return db.scalar(select(AgentRun).where(
        AgentRun.id == run_id, AgentRun.user_id == user_id,
    ))
