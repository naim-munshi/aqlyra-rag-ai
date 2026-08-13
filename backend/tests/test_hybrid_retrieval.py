import pytest
from sqlalchemy.orm import Session

from app.retrieval import (
    RetrievalHit,
    RetrievalQuery,
)
from app.services.hybrid_retrieval_service import (
    search_hybrid_chunks,
)
from app.services.lexical_retrieval_service import (
    LexicalRetrievalHit,
)

import app.services.hybrid_retrieval_service as hybrid_module


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.embed_calls = 0

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        assert text.strip()

        self.embed_calls += 1

        return [0.0] * 384


def make_vector_hit(
    chunk_id: str,
    similarity: float,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id="document-1",
        original_filename="test.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=1,
        source_label="Test",
        section_path=("Test",),
        content=f"Content for {chunk_id}",
        start_page=None,
        end_page=None,
        similarity_score=similarity,
        cosine_distance=1.0 - similarity,
        metadata={},
    )


def make_lexical_hit(
    chunk_id: str,
    score: float,
) -> LexicalRetrievalHit:
    return LexicalRetrievalHit(
        chunk_id=chunk_id,
        document_id="document-1",
        original_filename="test.md",
        parent_chunk_id=None,
        chunk_role="content",
        chunk_level=0,
        chunk_index=1,
        source_label="Test",
        section_path=("Test",),
        content=f"Content for {chunk_id}",
        start_page=None,
        end_page=None,
        lexical_score=score,
        metadata={},
    )


def test_hybrid_retrieval_fuses_both_rankings(
    monkeypatch,
    db_session: Session,
) -> None:
    vector_hits = [
        make_vector_hit(
            "chunk-a",
            0.95,
        ),
        make_vector_hit(
            "chunk-b",
            0.90,
        ),
        make_vector_hit(
            "chunk-c",
            0.80,
        ),
    ]

    lexical_hits = [
        make_lexical_hit(
            "chunk-b",
            0.9,
        ),
        make_lexical_hit(
            "chunk-d",
            0.8,
        ),
        make_lexical_hit(
            "chunk-c",
            0.7,
        ),
    ]

    fake_provider = FakeEmbeddingProvider()

    captured_top_k: list[int] = []

    def fake_vector_search(
        db,
        query,
        provider=None,
        query_vector=None,
    ):
        assert query_vector is not None

        captured_top_k.append(
            query.top_k
        )

        return vector_hits

    def fake_lexical_search(
        db,
        query,
    ):
        assert query.top_k == 8

        return lexical_hits

    def fake_score_specific_chunks(
        *,
        db,
        query,
        chunk_ids,
        provider=None,
        query_vector=None,
    ):
        assert query_vector is not None
        assert chunk_ids == (
            "chunk-d",
        )

        return {
            "chunk-d": make_vector_hit(
                "chunk-d",
                0.70,
            )
        }

    monkeypatch.setattr(
        hybrid_module,
        "create_configured_embedding_provider",
        lambda: fake_provider,
    )

    monkeypatch.setattr(
        hybrid_module,
        "search_similar_chunks",
        fake_vector_search,
    )

    monkeypatch.setattr(
        hybrid_module,
        "search_lexical_chunks",
        fake_lexical_search,
    )

    monkeypatch.setattr(
        hybrid_module,
        "score_specific_chunks",
        fake_score_specific_chunks,
    )

    results = search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id="user-1",
            text="security policy",
            top_k=2,
        ),
    )

    assert len(results) == 2
    assert results[0].chunk_id == "chunk-b"

    assert captured_top_k == [8]

    # Query embedding must only be generated once.
    assert fake_provider.embed_calls == 1

    # Semantic values retain dense-vector meaning.
    assert (
        results[0].similarity_score
        == pytest.approx(0.90)
    )

    assert (
        results[0].cosine_distance
        == pytest.approx(0.10)
    )

    # Hybrid/RRF ranking is a separate value.
    assert (
        results[0].ranking_score
        is not None
    )

    assert (
        results[0].ranking_score
        == pytest.approx(
            results[0].metadata[
                "hybrid_score"
            ]
        )
    )

    assert (
        results[0].metadata[
            "retrieval_mode"
        ]
        == "hybrid"
    )

    assert (
        results[0].metadata[
            "vector_rank"
        ]
        == 2
    )

    assert (
        results[0].metadata[
            "lexical_rank"
        ]
        == 1
    )

    assert (
        results[0].metadata[
            "semantic_similarity_score"
        ]
        == pytest.approx(0.90)
    )

    assert (
        results[0].metadata[
            "lexical_score"
        ]
        == pytest.approx(0.9)
    )

    assert (
        results[0].metadata[
            "retrieval_sources"
        ]
        == [
            "vector",
            "lexical",
        ]
    )


def test_hybrid_retrieval_can_keep_lexical_only_hit(
    monkeypatch,
    db_session: Session,
) -> None:
    fake_provider = FakeEmbeddingProvider()

    monkeypatch.setattr(
        hybrid_module,
        "create_configured_embedding_provider",
        lambda: fake_provider,
    )

    monkeypatch.setattr(
        hybrid_module,
        "search_similar_chunks",
        lambda **kwargs: [],
    )

    monkeypatch.setattr(
        hybrid_module,
        "search_lexical_chunks",
        lambda **kwargs: [
            make_lexical_hit(
                "exact-keyword",
                1.0,
            )
        ],
    )

    monkeypatch.setattr(
        hybrid_module,
        "score_specific_chunks",
        lambda **kwargs: {
            "exact-keyword": (
                make_vector_hit(
                    "exact-keyword",
                    0.25,
                )
            )
        },
    )

    results = search_hybrid_chunks(
        db=db_session,
        query=RetrievalQuery(
            user_id="user-1",
            text="quantumfalcon",
            top_k=5,
        ),
    )

    assert len(results) == 1

    assert (
        results[0].chunk_id
        == "exact-keyword"
    )

    # Lexical candidate gets a real dense score,
    # but it was not a vector top-K candidate.
    assert (
        results[0].similarity_score
        == pytest.approx(0.25)
    )

    assert (
        results[0].cosine_distance
        == pytest.approx(0.75)
    )

    assert (
        results[0].ranking_score
        is not None
    )

    assert (
        results[0].metadata[
            "vector_rank"
        ]
        is None
    )

    assert (
        results[0].metadata[
            "lexical_rank"
        ]
        == 1
    )

    assert (
        results[0].metadata[
            "retrieval_sources"
        ]
        == ["lexical"]
    )

    assert fake_provider.embed_calls == 1
