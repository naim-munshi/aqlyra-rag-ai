from app.llms import (
    LLMProvider,
    create_configured_llm_provider,
)
from app.rag.answer_types import (
    GroundedAnswerDraft,
    GroundedAnswerGenerationError,
)
from app.rag.prompt_builder import (
    build_grounded_prompt,
)
from app.rag.types import EvidenceContext


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

    answer_text = generation.text.strip()

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
