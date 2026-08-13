from dataclasses import dataclass

import pytest

import app.retrieval.benchmark as benchmark_module

from app.reranking import RerankerInfo
from app.retrieval.benchmark import (
    RetrievalBenchmarkSpec,
    run_retrieval_benchmark,
)
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
)


@dataclass(frozen=True)
class FakeEmbeddingInfo:
    provider_name: str = "fake-semantic"
    model_name: str = "fake-embedding"


class FakeEmbeddingProvider:
    info = FakeEmbeddingInfo()


@dataclass(frozen=True)
class FakeHit:
    chunk_id: str


class FakeReranker:
    @property
    def info(self) -> RerankerInfo:
        return RerankerInfo(
            provider_name="fake-reranker",
            model_name="fake-reranker-v1",
        )


def test_benchmark_compares_hybrid_and_reranked(
    monkeypatch,
) -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="q1",
            query="question",
            relevant_chunk_ids=(
                frozenset({"relevant"})
            ),
        ),
    )

    monkeypatch.setattr(
        benchmark_module,
        "resolve_evaluation_cases",
        lambda **kwargs: cases,
    )

    monkeypatch.setattr(
        benchmark_module,
        "search_similar_chunks",
        lambda **kwargs: [
            FakeHit("noise")
        ],
    )

    hybrid_hits = [
        FakeHit("noise"),
        FakeHit("relevant"),
    ]

    monkeypatch.setattr(
        benchmark_module,
        "search_hybrid_chunks",
        lambda **kwargs: hybrid_hits,
    )

    def fake_rerank_hits(
        *,
        query_text,
        hits,
        reranker,
        fallback_on_error,
    ):
        assert query_text == "question"
        assert hits is hybrid_hits
        assert fallback_on_error is False

        return [
            FakeHit("relevant"),
            FakeHit("noise"),
        ]

    monkeypatch.setattr(
        benchmark_module,
        "rerank_hits",
        fake_rerank_hits,
    )

    report = run_retrieval_benchmark(
        db=None,
        user_id="user-1",
        specs=(
            RetrievalBenchmarkSpec(
                query_id="placeholder",
                query="placeholder",
                document_filename="doc.md",
                evidence_marker="marker",
            ),
        ),
        k=1,
        retrieval_depth=2,
        provider=FakeEmbeddingProvider(),
        reranker=FakeReranker(),
    )

    assert (
        report.hybrid.hit_rate_at_k
        == pytest.approx(0.0)
    )

    assert report.reranked is not None

    assert (
        report.reranked.hit_rate_at_k
        == pytest.approx(1.0)
    )

    assert (
        report.rerank_hit_rate_delta
        == pytest.approx(1.0)
    )

    assert (
        report.rerank_recall_delta
        == pytest.approx(1.0)
    )

    assert (
        report.rerank_mrr_delta
        == pytest.approx(1.0)
    )

    assert (
        report.reranker_provider_name
        == "fake-reranker"
    )
