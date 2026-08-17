import re

from app.llms import (
    LLMProvider,
    create_configured_llm_provider,
)
from app.rag.answer_types import (
    GroundedAnswerDraft,
    GroundedAnswerGenerationError,
    INSUFFICIENT_EVIDENCE_SENTINEL,
)
from app.rag.prompt_builder import (
    build_grounded_prompt,
)
from app.rag.types import EvidenceContext


_CITATION_TYPOGRAPHY_PATTERN = re.compile(
    r"【(S[1-9][0-9]*)】"
)

_CITATION_SPACING_PATTERN = re.compile(
    r"(?<!\\s)(\\[S[1-9][0-9]*\\])"
)


def _normalize_generated_citation_syntax(
    text: str,
) -> str:
    """
    Canonicalize a known LLM typography variant.

    Validation remains strict after normalization.
    Unknown source IDs are still rejected by the
    citation validator.
    """
    normalized = (
        _CITATION_TYPOGRAPHY_PATTERN.sub(
            lambda match: (
                f"[{match.group(1)}]"
            ),
            text,
        )
    )

    return _CITATION_SPACING_PATTERN.sub(
        r" \\1",
        normalized,
    )


CITATION_REPAIR_INSTRUCTIONS = f"""
You are repairing a grounded answer that failed citation
validation.

Follow these rules:

1. Use only the supplied evidence.
2. Preserve the meaning of the original answer when supported.
3. Do not add new factual claims.
4. Remove any claim that cannot be supported by the evidence.
5. Every evidence-derived block must contain at least one
    valid citation in the exact format [S1], [S2], and so on.
    This includes factual paragraphs, bullets, numbered items,
    headings, and subheadings. Put the citation in the same block.
6. Use only the source IDs listed in the request.
7. Never invent source IDs.
8. Keep the answer in the same language as the original answer.
9. Return only the repaired answer. Do not explain the repair.
10. If the evidence cannot support any useful answer, output
    exactly:

{INSUFFICIENT_EVIDENCE_SENTINEL}
""".strip()


def _sum_optional(
    first: int | None,
    second: int | None,
) -> int | None:
    if first is None and second is None:
        return None

    return (first or 0) + (second or 0)


def generate_grounded_answer_draft(
    *,
    question: str,
    evidence_context: EvidenceContext,
    provider: LLMProvider | None = None,
) -> GroundedAnswerDraft:
    prompt = build_grounded_prompt(
        question=question,
        evidence_context=evidence_context,
    )

    active_provider = (
        provider
        or create_configured_llm_provider()
    )

    generation = active_provider.generate(
        instructions=prompt.instructions,
        input_text=prompt.input_text,
    )

    answer_text = _normalize_generated_citation_syntax(
        generation.text.strip()
    )

    if not answer_text:
        raise GroundedAnswerGenerationError(
            "LLM provider returned an empty answer"
        )

    return GroundedAnswerDraft(
        question=question.strip(),
        answer_text=answer_text,
        sources=evidence_context.sources,
        provider_name=(
            generation.provider_name
        ),
        model_name=generation.model_name,
        response_id=generation.response_id,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        total_tokens=generation.total_tokens,
        evidence_tokens=(
            evidence_context.estimated_tokens
        ),
        skipped_evidence_count=(
            evidence_context.skipped_count
        ),
        evidence_was_truncated=(
            evidence_context.was_truncated
        ),
    )


def repair_grounded_answer_draft(
    *,
    draft: GroundedAnswerDraft,
    evidence_context: EvidenceContext,
    provider: LLMProvider,
) -> GroundedAnswerDraft:
    allowed_source_ids = ", ".join(
        f"[{source.source_id}]"
        for source in evidence_context.sources
    )

    repair_input = (
        "QUESTION\n"
        "--------\n"
        f"{draft.question}\n\n"
        "AVAILABLE SOURCE IDS\n"
        "--------------------\n"
        f"{allowed_source_ids}\n\n"
        "ORIGINAL ANSWER\n"
        "---------------\n"
        f"{draft.answer_text}\n\n"
        "EVIDENCE\n"
        "--------\n"
        f"{evidence_context.text.strip()}"
    )

    generation = provider.generate(
        instructions=(
            CITATION_REPAIR_INSTRUCTIONS
        ),
        input_text=repair_input,
    )

    repaired_text = _normalize_generated_citation_syntax(
        generation.text.strip()
    )

    if not repaired_text:
        raise GroundedAnswerGenerationError(
            "LLM provider returned an empty "
            "citation-repair answer"
        )

    return GroundedAnswerDraft(
        question=draft.question,
        answer_text=repaired_text,
        sources=evidence_context.sources,
        provider_name=(
            generation.provider_name
        ),
        model_name=generation.model_name,
        response_id=generation.response_id,
        input_tokens=_sum_optional(
            draft.input_tokens,
            generation.input_tokens,
        ),
        output_tokens=_sum_optional(
            draft.output_tokens,
            generation.output_tokens,
        ),
        total_tokens=_sum_optional(
            draft.total_tokens,
            generation.total_tokens,
        ),
        evidence_tokens=(
            evidence_context.estimated_tokens
        ),
        skipped_evidence_count=(
            evidence_context.skipped_count
        ),
        evidence_was_truncated=(
            evidence_context.was_truncated
        ),
    )