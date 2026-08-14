from types import SimpleNamespace

import app.retrieval.reranking_benchmark as benchmark_module

from app.query_rewriting import QueryRewriterInfo
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
)


class CountingRewriter:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def info(self) -> QueryRewriterInfo:
        return QueryRewriterInfo(
            provider_name="test-rewriter",
            model_name="test-rewriter-v1",
        )

    def rewrite(
        self,
        query: str,
    ) -> str:
        self.calls += 1

        assert query == "original question"

        return "rewritten retrieval query"


class CountingReranker:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def info(self):
        return SimpleNamespace(
            provider_name="test-reranker",
            model_name="test-reranker-v1",
        )

    def rerank(
        self,
        *,
        query,
        hits,
    ):
        raise AssertionError(
            "rerank_hits should be monkeypatched"
        )


def test_multik_rewrite_and_rerank_once_per_case(
    monkeypatch,
) -> None:
    case = RetrievalEvaluationCase(
        query_id="case-1",
        query="original question",
        relevant_chunk_ids=frozenset(
            {"relevant"}
        ),
    )

    monkeypatch.setattr(
        benchmark_module,
        "resolve_evaluation_cases",
        lambda **kwargs: (case,),
    )

    captured = {
        "vector": [],
        "hybrid": [],
        "reranker": [],
    }

    def fake_vector(
        *,
        db,
        query,
        provider,
    ):
        captured["vector"].append(
            query.text
        )

        return [
            SimpleNamespace(
                chunk_id="relevant"
            )
        ]

    def fake_hybrid(
        *,
        db,
        query,
        provider,
    ):
        captured["hybrid"].append(
            query.text
        )

        return [
            SimpleNamespace(
                chunk_id="relevant"
            )
        ]

    reranker = CountingReranker()

    def fake_rerank(
        *,
        query_text,
        hits,
        reranker,
        fallback_on_error,
    ):
        reranker.calls += 1
        captured["reranker"].append(
            query_text
        )

        return hits

    monkeypatch.setattr(
        benchmark_module,
        "search_similar_chunks",
        fake_vector,
    )

    monkeypatch.setattr(
        benchmark_module,
        "search_hybrid_chunks",
        fake_hybrid,
    )

    monkeypatch.setattr(
        benchmark_module,
        "rerank_hits",
        fake_rerank,
    )

    provider = SimpleNamespace(
        info=SimpleNamespace(
            provider_name="deterministic",
            model_name="test",
        )
    )

    rewriter = CountingRewriter()

    report = (
        benchmark_module
        .run_reranking_benchmark_once(
            db=None,
            user_id="user-1",
            specs=(object(),),
            reranker=reranker,
            query_rewriter=rewriter,
            ks=(1, 3, 5),
            retrieval_depth=5,
            provider=provider,
            delay_seconds=0,
        )
    )

    assert rewriter.calls == 1
    assert reranker.calls == 1

    assert captured["vector"] == [
        "rewritten retrieval query"
    ]

    assert captured["hybrid"] == [
        "rewritten retrieval query"
    ]

    assert captured["reranker"] == [
        "original question"
    ]

    assert len(report.results) == 3

    assert (
        report.query_rewriter_provider_name
        == "test-rewriter"
    )

    assert (
        report.query_rewriter_model_name
        == "test-rewriter-v1"
    )
