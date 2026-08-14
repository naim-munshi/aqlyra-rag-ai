from types import SimpleNamespace

import app.retrieval.benchmark as benchmark_module

from app.query_rewriting import QueryRewriterInfo
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
)


class FakeQueryRewriter:
    @property
    def info(self) -> QueryRewriterInfo:
        return QueryRewriterInfo(
            provider_name="test-rewriter",
            model_name="test-v1",
        )

    def rewrite(
        self,
        query: str,
    ) -> str:
        assert query == "original question"

        return "rewritten retrieval query"


class FakeReranker:
    @property
    def info(self):
        return SimpleNamespace(
            provider_name="test-reranker",
            model_name="test-reranker-v1",
        )


def test_benchmark_rewrites_retrieval_but_not_reranker(
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

    def fake_rerank(
        *,
        query_text,
        hits,
        reranker,
        fallback_on_error,
    ):
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

    report = (
        benchmark_module.run_retrieval_benchmark(
            db=None,
            user_id="user-1",
            specs=(object(),),
            k=1,
            retrieval_depth=1,
            provider=provider,
            reranker=FakeReranker(),
            query_rewriter=FakeQueryRewriter(),
        )
    )

    assert captured["vector"] == [
        "rewritten retrieval query"
    ]

    assert captured["hybrid"] == [
        "rewritten retrieval query"
    ]

    assert captured["reranker"] == [
        "original question"
    ]

    assert (
        report.query_rewriter_provider_name
        == "test-rewriter"
    )

    assert (
        report.query_rewriter_model_name
        == "test-v1"
    )
