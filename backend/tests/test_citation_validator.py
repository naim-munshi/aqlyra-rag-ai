import pytest

from app.rag import (
    CitationValidationError,
    EvidenceSource,
    GroundedAnswerDraft,
    INSUFFICIENT_EVIDENCE_SENTINEL,
    MalformedCitationError,
    MissingCitationError,
    UncitedClaimError,
    UnknownCitationError,
    validate_grounded_answer_draft,
)


def create_source(
    source_id: str,
    *,
    chunk_index: int,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        chunk_id=f"chunk-{source_id}",
        document_id="document-1",
        original_filename="security.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=chunk_index,
        source_label="Security",
        section_path=("Security",),
        start_page=chunk_index + 1,
        end_page=chunk_index + 1,
        similarity_score=0.95,
        content=(
            f"Evidence for {source_id}."
        ),
        was_truncated=False,
    )


def create_draft(
    answer_text: str,
) -> GroundedAnswerDraft:
    return GroundedAnswerDraft(
        question=(
            "How is private data protected?"
        ),
        answer_text=answer_text,
        sources=(
            create_source(
                "S1",
                chunk_index=0,
            ),
            create_source(
                "S2",
                chunk_index=1,
            ),
        ),
        provider_name="test-provider",
        model_name="test-model",
        response_id="response-1",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        evidence_tokens=50,
        skipped_evidence_count=0,
        evidence_was_truncated=False,
    )


def test_validator_accepts_valid_cited_answer(
) -> None:
    draft = create_draft(
        "JWT protects authenticated routes "
        "[S1].\n\n"
        "Document queries are filtered by "
        "owner [S2]."
    )

    result = (
        validate_grounded_answer_draft(
            draft
        )
    )

    assert result.is_refusal is False

    assert result.citation_ids == (
        "S1",
        "S2",
    )

    assert result.citation_count == 2

    assert tuple(
        source.source_id
        for source in result.cited_sources
    ) == (
        "S1",
        "S2",
    )


def test_validator_preserves_first_use_order(
) -> None:
    draft = create_draft(
        "Ownership is enforced [S2], "
        "while authentication uses JWT "
        "[S1] [S2]."
    )

    result = (
        validate_grounded_answer_draft(
            draft
        )
    )

    assert result.citation_ids == (
        "S2",
        "S1",
    )

    assert result.citation_count == 3


def test_validator_rejects_unknown_citation(
) -> None:
    draft = create_draft(
        "The system uses an unknown "
        "source [S3]."
    )

    with pytest.raises(
        UnknownCitationError
    ):
        validate_grounded_answer_draft(
            draft
        )


def test_validator_rejects_missing_citation(
) -> None:
    draft = create_draft(
        "JWT protects authenticated routes."
    )

    with pytest.raises(
        MissingCitationError
    ):
        validate_grounded_answer_draft(
            draft
        )


def test_validator_rejects_uncited_block(
) -> None:
    draft = create_draft(
        "JWT protects authenticated routes "
        "[S1].\n\n"
        "Documents are isolated by owner."
    )

    with pytest.raises(
        UncitedClaimError
    ):
        validate_grounded_answer_draft(
            draft
        )


def test_validator_allows_headings_and_labels(
) -> None:
    draft = create_draft(
        "## Summary\n\n"
        "JWT protects private routes [S1].\n\n"
        "Additional detail:\n\n"
        "Document access is owner-filtered "
        "[S2]."
    )

    result = (
        validate_grounded_answer_draft(
            draft
        )
    )

    assert result.citation_ids == (
        "S1",
        "S2",
    )


def test_validator_accepts_exact_refusal(
) -> None:
    draft = create_draft(
        INSUFFICIENT_EVIDENCE_SENTINEL
    )

    result = (
        validate_grounded_answer_draft(
            draft
        )
    )

    assert result.is_refusal is True
    assert result.citation_ids == ()
    assert result.cited_sources == ()
    assert result.citation_count == 0


def test_validator_rejects_mixed_refusal(
) -> None:
    draft = create_draft(
        INSUFFICIENT_EVIDENCE_SENTINEL
        + " because the document is missing."
    )

    with pytest.raises(
        CitationValidationError
    ):
        validate_grounded_answer_draft(
            draft
        )


def test_validator_rejects_malformed_citation(
) -> None:
    draft = create_draft(
        "JWT protects private routes [s1]."
    )

    with pytest.raises(
        MalformedCitationError
    ):
        validate_grounded_answer_draft(
            draft
        )
