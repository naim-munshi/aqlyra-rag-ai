from types import SimpleNamespace

import app.services.rag_answer_service as rag_module

from app.reranking import (
    RerankerValidationError,
)
from app.retrieval import RetrievalQuery


def make_query(
    *,
    top_k: int = 8,
) -> RetrievalQuery:
    return RetrievalQuery(
        user_id="user-1",
        text="Which evidence is relevant?",
        top_k=top_k,
    )


def test_rag_uses_hybrid_when_reranking_disabled(
    monkeypatch,
) -> None:
    hybrid_hits = [object()]

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        False,
    )

    monkeypatch.setattr(
        rag_module,
        "search_hybrid_chunks",
        lambda **kwargs: hybrid_hits,
    )

    def fail_reranked(**kwargs):
        raise AssertionError(
            "Reranked retrieval should not run"
        )

    monkeypatch.setattr(
        rag_module,
        "search_reranked_chunks",
        fail_reranked,
    )

    result = rag_module._retrieve_rag_hits(
        db=None,
        query=make_query(),
    )

    assert result is hybrid_hits


def test_rag_uses_reranker_when_enabled(
    monkeypatch,
) -> None:
    reranked_hits = [object()]
    fake_reranker = SimpleNamespace()

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        True,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "RERANKER_CANDIDATE_DEPTH",
        15,
    )

    captured = {}

    def fake_reranked_search(
        *,
        db,
        query,
        reranker,
        candidate_depth,
        fallback_on_error,
    ):
        captured["top_k"] = query.top_k
        captured["reranker"] = reranker
        captured["candidate_depth"] = (
            candidate_depth
        )
        captured["fallback"] = (
            fallback_on_error
        )

        return reranked_hits

    monkeypatch.setattr(
        rag_module,
        "search_reranked_chunks",
        fake_reranked_search,
    )

    result = rag_module._retrieve_rag_hits(
        db=None,
        query=make_query(top_k=8),
        reranker=fake_reranker,
    )

    assert result is reranked_hits
    assert captured["top_k"] == 8
    assert (
        captured["reranker"]
        is fake_reranker
    )
    assert captured["candidate_depth"] == 15
    assert captured["fallback"] is True


def test_rag_falls_back_when_reranker_configuration_fails(
    monkeypatch,
) -> None:
    hybrid_hits = [object()]

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        True,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "RERANKER_CANDIDATE_DEPTH",
        15,
    )

    def fail_configuration():
        raise RerankerValidationError(
            "provider unavailable"
        )

    monkeypatch.setattr(
        rag_module,
        "create_configured_reranker",
        fail_configuration,
    )

    monkeypatch.setattr(
        rag_module,
        "search_hybrid_chunks",
        lambda **kwargs: hybrid_hits,
    )

    result = rag_module._retrieve_rag_hits(
        db=None,
        query=make_query(),
    )

    assert result is hybrid_hits


def test_rag_uses_hybrid_when_top_k_exceeds_candidate_depth(
    monkeypatch,
) -> None:
    hybrid_hits = [object()]

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        True,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "RERANKER_CANDIDATE_DEPTH",
        15,
    )

    monkeypatch.setattr(
        rag_module,
        "search_hybrid_chunks",
        lambda **kwargs: hybrid_hits,
    )

    def fail_reranked(**kwargs):
        raise AssertionError(
            "Reranker should not run when "
            "top_k exceeds candidate depth"
        )

    monkeypatch.setattr(
        rag_module,
        "search_reranked_chunks",
        fail_reranked,
    )

    result = rag_module._retrieve_rag_hits(
        db=None,
        query=make_query(top_k=20),
    )

    assert result is hybrid_hits


def test_reranked_evidence_becomes_first_grounded_source(
    monkeypatch,
) -> None:
    from app.llms import create_llm_provider
    from app.reranking import (
        RerankerInfo,
        RerankerScore,
    )
    from app.retrieval import RetrievalHit
    from app.services.rag_answer_service import (
        answer_question,
    )

    relevant_chunk_id = "relevant-chunk"

    def make_hit(
        chunk_id: str,
        ranking_score: float,
    ) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=chunk_id,
            document_id="doc-1",
            original_filename="security.md",
            parent_chunk_id=None,
            chunk_role="content",
            chunk_level=0,
            chunk_index=1,
            source_label="Security",
            section_path=("Security",),
            content=(
                "The annual security review "
                "takes place in October."
                if chunk_id == relevant_chunk_id
                else "Unrelated evidence."
            ),
            start_page=None,
            end_page=None,
            similarity_score=0.5,
            cosine_distance=0.5,
            ranking_score=ranking_score,
            metadata={
                "retrieval_mode": "hybrid",
                "hybrid_score": ranking_score,
            },
        )

    hybrid_hits = [
        make_hit(
            "noise-a",
            0.90,
        ),
        make_hit(
            "noise-b",
            0.80,
        ),
        make_hit(
            relevant_chunk_id,
            0.20,
        ),
    ]

    class PromoteRelevantReranker:
        @property
        def info(self) -> RerankerInfo:
            return RerankerInfo(
                provider_name="test-reranker",
                model_name="test-reranker-v1",
            )

        def rerank(
            self,
            *,
            query,
            hits,
        ):
            return tuple(
                RerankerScore(
                    chunk_id=hit.chunk_id,
                    score=(
                        1.0
                        if (
                            hit.chunk_id
                            == relevant_chunk_id
                        )
                        else 0.1
                    ),
                )
                for hit in hits
            )

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        True,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "RERANKER_CANDIDATE_DEPTH",
        15,
    )

    import app.services.reranked_retrieval_service as reranked_service_module

    monkeypatch.setattr(
        reranked_service_module,
        "search_hybrid_chunks",
        lambda **kwargs: hybrid_hits,
    )

    answer_provider = create_llm_provider(
        provider_name="deterministic",
    )

    result = answer_question(
        db=None,
        user_id="user-1",
        question=(
            "When is the annual "
            "security review?"
        ),
        top_k=3,
        chunk_roles=("content",),
        provider=answer_provider,
        reranker=PromoteRelevantReranker(),
    )

    assert result.is_refusal is False
    assert result.citation_count == 1

    first = result.citations[0]

    assert first.source_id == "S1"
    assert (
        first.chunk_id
        == relevant_chunk_id
    )
    assert (
        first.original_filename
        == "security.md"
    )
