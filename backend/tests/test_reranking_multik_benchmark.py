from dataclasses import dataclass

import pytest

import app.retrieval.reranking_benchmark as module

from app.reranking import (
    RerankerInfo,
    RerankerScore,
)
from app.retrieval.benchmark import (
    RetrievalBenchmarkSpec,
)
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
)
from app.retrieval.reranking_benchmark import (
    run_reranking_benchmark_once,
)


@dataclass(frozen=True)
class FakeEmbeddingInfo:
    provider_name: str = "fake"
    model_name: str = "fake-embedding"


class FakeEmbeddingProvider:
    info = FakeEmbeddingInfo()


@dataclass(frozen=True)
class FakeHit:
    chunk_id: str


class CountingReranker:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def info(self) -> RerankerInfo:
        return RerankerInfo(
            provider_name="counting",
            model_name="counting-v1",
        )

    def rerank(self, *, query, hits):
        self.calls += 1

        return tuple(
            RerankerScore(
                chunk_id=hit.chunk_id,
                score=(
                    1.0
                    if hit.chunk_id == "relevant"
                    else 0.1
                ),
            )
            for hit in hits
        )


def test_multik_uses_one_rerank_per_case(
    monkeypatch,
) -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="q1",
            query="question one",
            relevant_chunk_ids=(
                frozenset({"relevant"})
            ),
        ),
        RetrievalEvaluationCase(
            query_id="q2",
            query="question two",
            relevant_chunk_ids=(
                frozenset({"relevant"})
            ),
        ),
    )

    monkeypatch.setattr(
        module,
        "resolve_evaluation_cases",
        lambda **kwargs: cases,
    )

    monkeypatch.setattr(
        module,
        "search_similar_chunks",
        lambda **kwargs: [
            FakeHit("noise"),
        ],
    )

    monkeypatch.setattr(
        module,
        "search_hybrid_chunks",
        lambda **kwargs: [
            FakeHit("noise"),
            FakeHit("relevant"),
        ],
    )

    def fake_rerank_hits(
        *,
        query_text,
        hits,
        reranker,
        fallback_on_error,
    ):
        scores = reranker.rerank(
            query=query_text,
            hits=tuple(hits),
        )

        score_map = {
            score.chunk_id: score.score
            for score in scores
        }

        return sorted(
            hits,
            key=lambda hit: (
                -score_map[hit.chunk_id]
            ),
        )

    monkeypatch.setattr(
        module,
        "rerank_hits",
        fake_rerank_hits,
    )

    reranker = CountingReranker()

    report = run_reranking_benchmark_once(
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
        reranker=reranker,
        ks=(1, 2),
        retrieval_depth=2,
        provider=FakeEmbeddingProvider(),
        delay_seconds=0,
    )

    assert reranker.calls == 2
    assert len(report.results) == 2

    at_one = report.results[0]

    assert at_one.k == 1

    assert (
        at_one.hybrid.hit_rate_at_k
        == pytest.approx(0.0)
    )

    assert (
        at_one.reranked.hit_rate_at_k
        == pytest.approx(1.0)
    )
