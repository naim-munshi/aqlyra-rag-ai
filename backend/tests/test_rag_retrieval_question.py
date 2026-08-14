import app.services.rag_answer_service as rag_module

from app.llms.deterministic_provider import (
    DeterministicLLMProvider,
)
from app.retrieval import RetrievalHit


def test_explicit_retrieval_question_is_used_for_search(
    monkeypatch,
) -> None:
    captured = {}

    def fake_retrieve(
        *,
        db,
        query,
        reranker=None,
        query_rewriter=None,
    ):
        captured["query_text"] = query.text
        return []

    monkeypatch.setattr(
        rag_module,
        "_retrieve_rag_hits",
        fake_retrieve,
    )

    result = rag_module.answer_question(
        db=None,
        user_id="user-1",
        question="What about the second rule?",
        retrieval_question=(
            "What is the second password "
            "rotation rule?"
        ),
        provider=DeterministicLLMProvider(),
    )

    assert captured["query_text"] == (
        "What is the second password "
        "rotation rule?"
    )

    assert result.question == (
        "What about the second rule?"
    )


def test_blank_retrieval_question_falls_back_to_original(
    monkeypatch,
) -> None:
    captured = {}

    def fake_retrieve(
        *,
        db,
        query,
        reranker=None,
        query_rewriter=None,
    ):
        captured["query_text"] = query.text
        return []

    monkeypatch.setattr(
        rag_module,
        "_retrieve_rag_hits",
        fake_retrieve,
    )

    rag_module.answer_question(
        db=None,
        user_id="user-1",
        question="Original question",
        retrieval_question="   ",
        provider=DeterministicLLMProvider(),
    )

    assert captured["query_text"] == (
        "Original question"
    )


def test_grounded_generation_keeps_original_question(
    monkeypatch,
) -> None:
    captured = {}

    hit = RetrievalHit(
        chunk_id="chunk-1",
        document_id="document-1",
        original_filename="policy.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=0,
        source_label="Password Policy",
        section_path=("Password Policy",),
        content=(
            "The second password rule requires "
            "rotation every 90 days."
        ),
        start_page=None,
        end_page=None,
        similarity_score=0.95,
        cosine_distance=0.05,
        metadata={},
    )

    def fake_retrieve(
        *,
        db,
        query,
        reranker=None,
        query_rewriter=None,
    ):
        captured["retrieval_question"] = (
            query.text
        )

        return [hit]

    original_generate = (
        rag_module.generate_grounded_answer_draft
    )

    def capture_generate(
        *,
        question,
        evidence_context,
        provider,
    ):
        captured["generation_question"] = (
            question
        )

        return original_generate(
            question=question,
            evidence_context=evidence_context,
            provider=provider,
        )

    monkeypatch.setattr(
        rag_module,
        "_retrieve_rag_hits",
        fake_retrieve,
    )

    monkeypatch.setattr(
        rag_module,
        "generate_grounded_answer_draft",
        capture_generate,
    )

    result = rag_module.answer_question(
        db=None,
        user_id="user-1",
        question="What about the second rule?",
        retrieval_question=(
            "What is the second password "
            "rotation rule?"
        ),
        provider=DeterministicLLMProvider(),
    )

    assert captured["retrieval_question"] == (
        "What is the second password "
        "rotation rule?"
    )

    assert captured["generation_question"] == (
        "What about the second rule?"
    )

    assert result.question == (
        "What about the second rule?"
    )

    assert result.answer_text == (
        "Deterministic grounded answer [S1]."
    )
