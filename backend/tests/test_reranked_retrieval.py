import json
from dataclasses import dataclass

import pytest

from app.llms.types import (
    LLMGeneration,
    LLMProviderInfo,
)
from app.reranking import (
    IdentityReranker,
    LLMReranker,
    RerankerValidationError,
)
from app.retrieval import (
    RetrievalHit,
    RetrievalQuery,
)
from app.services.reranked_retrieval_service import (
    search_reranked_chunks,
)

import app.services.reranked_retrieval_service as reranked_module


def make_hit(
    chunk_id: str,
    ranking_score: float,
    similarity_score: float,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id="doc-1",
        original_filename="test.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=1,
        source_label="Test",
        section_path=("Test",),
        content=f"Evidence {chunk_id}",
        start_page=None,
        end_page=None,
        similarity_score=(
            similarity_score
        ),
        cosine_distance=(
            1.0 - similarity_score
        ),
        ranking_score=(
            ranking_score
        ),
        metadata={
            "retrieval_mode": "hybrid",
            "hybrid_score": ranking_score,
        },
    )


@dataclass
class FakeLLMProvider:
    response_text: str

    @property
    def info(self) -> LLMProviderInfo:
        return LLMProviderInfo(
            provider_name="fake",
            model_name="fake-model",
            max_output_tokens=800,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
    ) -> LLMGeneration:
        assert "untrusted" in instructions

        payload = json.loads(
            input_text
        )

        assert payload["query"]

        return LLMGeneration(
            text=self.response_text,
            provider_name="fake",
            model_name="fake-model",
        )


def test_identity_reranker_preserves_order():
    hits = (
        make_hit(
            "a",
            0.9,
            0.8,
        ),
        make_hit(
            "b",
            0.8,
            0.7,
        ),
    )

    results = IdentityReranker().rerank(
        query="question",
        hits=hits,
    )

    assert [
        result.chunk_id
        for result in results
    ] == [
        "a",
        "b",
    ]

    assert (
        results[0].score
        > results[1].score
    )


def test_llm_reranker_validates_and_scores():
    provider = FakeLLMProvider(
        response_text=json.dumps(
            {
                "scores": [
                    {
                        "id": "C1",
                        "score": 0.2,
                    },
                    {
                        "id": "C2",
                        "score": 0.95,
                    },
                ]
            }
        )
    )

    reranker = LLMReranker(
        provider=provider
    )

    results = reranker.rerank(
        query="Which evidence matters?",
        hits=(
            make_hit(
                "a",
                0.9,
                0.8,
            ),
            make_hit(
                "b",
                0.8,
                0.7,
            ),
        ),
    )

    assert {
        result.chunk_id: result.score
        for result in results
    } == {
        "a": 0.2,
        "b": 0.95,
    }


def test_llm_reranker_rejects_missing_candidate():
    provider = FakeLLMProvider(
        response_text=json.dumps(
            {
                "scores": [
                    {
                        "id": "C1",
                        "score": 0.9,
                    }
                ]
            }
        )
    )

    reranker = LLMReranker(
        provider=provider
    )

    with pytest.raises(
        RerankerValidationError,
        match="every candidate",
    ):
        reranker.rerank(
            query="question",
            hits=(
                make_hit(
                    "a",
                    0.9,
                    0.8,
                ),
                make_hit(
                    "b",
                    0.8,
                    0.7,
                ),
            ),
        )


def test_reranked_search_reorders_without_corrupting_semantic_scores(
    monkeypatch,
):
    hybrid_hits = [
        make_hit(
            "a",
            0.90,
            0.91,
        ),
        make_hit(
            "b",
            0.80,
            0.42,
        ),
        make_hit(
            "c",
            0.70,
            0.75,
        ),
    ]

    captured_top_k = []

    def fake_hybrid_search(
        *,
        db,
        query,
        provider=None,
    ):
        captured_top_k.append(
            query.top_k
        )

        return hybrid_hits

    monkeypatch.setattr(
        reranked_module,
        "search_hybrid_chunks",
        fake_hybrid_search,
    )

    provider = FakeLLMProvider(
        response_text=json.dumps(
            {
                "scores": [
                    {
                        "id": "C1",
                        "score": 0.10,
                    },
                    {
                        "id": "C2",
                        "score": 0.99,
                    },
                    {
                        "id": "C3",
                        "score": 0.50,
                    },
                ]
            }
        )
    )

    results = search_reranked_chunks(
        db=None,
        query=RetrievalQuery(
            user_id="user-1",
            text="question",
            top_k=2,
        ),
        reranker=LLMReranker(
            provider=provider
        ),
        candidate_depth=3,
    )

    assert captured_top_k == [3]

    assert [
        hit.chunk_id
        for hit in results
    ] == [
        "b",
        "c",
    ]

    # Dense-vector semantics remain untouched.
    assert (
        results[0].similarity_score
        == pytest.approx(0.42)
    )

    assert (
        results[0].cosine_distance
        == pytest.approx(0.58)
    )

    # Final ranking is explicitly separate.
    assert (
        results[0].ranking_score
        == pytest.approx(0.99)
    )

    assert (
        results[0].metadata[
            "hybrid_score"
        ]
        == pytest.approx(0.80)
    )

    assert (
        results[0].metadata[
            "pre_rerank_rank"
        ]
        == 2
    )

    assert (
        results[0].metadata[
            "post_rerank_rank"
        ]
        == 1
    )

    assert (
        results[0].metadata[
            "retrieval_mode"
        ]
        == "hybrid_reranked"
    )
