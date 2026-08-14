import app.services.rag_answer_service as rag_module

from app.query_rewriting import (
    QueryRewriterInfo,
    QueryRewriteValidationError,
)
from app.retrieval import RetrievalQuery


class FakeQueryRewriter:
    @property
    def info(self) -> QueryRewriterInfo:
        return QueryRewriterInfo(
            provider_name="test",
            model_name="test-v1",
        )

    def rewrite(
        self,
        query: str,
    ) -> str:
        return (
            "yearly security assessment scheduled month"
        )


class FailingQueryRewriter(
    FakeQueryRewriter
):
    def rewrite(
        self,
        query: str,
    ) -> str:
        raise QueryRewriteValidationError(
            "unsafe rewrite"
        )


def make_query() -> RetrievalQuery:
    return RetrievalQuery(
        user_id="user-1",
        text=(
            "Which month is the yearly "
            "security assessment scheduled?"
        ),
        top_k=5,
        chunk_roles=("content",),
    )


def test_query_rewrite_disabled_preserves_original(
    monkeypatch,
) -> None:
    query = make_query()

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        False,
    )

    result = (
        rag_module._rewrite_retrieval_query(
            query=query,
            query_rewriter=FakeQueryRewriter(),
        )
    )

    assert result is query
    assert result.text == query.text


def test_query_rewrite_enabled_changes_only_retrieval_text(
    monkeypatch,
) -> None:
    query = make_query()

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        True,
    )

    result = (
        rag_module._rewrite_retrieval_query(
            query=query,
            query_rewriter=FakeQueryRewriter(),
        )
    )

    assert result is not query
    assert result.text == (
        "yearly security assessment scheduled month"
    )

    assert query.text == (
        "Which month is the yearly "
        "security assessment scheduled?"
    )


def test_query_rewrite_failure_falls_back_to_original(
    monkeypatch,
) -> None:
    query = make_query()

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        True,
    )

    result = (
        rag_module._rewrite_retrieval_query(
            query=query,
            query_rewriter=FailingQueryRewriter(),
        )
    )

    assert result is query


def test_hybrid_receives_rewritten_query(
    monkeypatch,
) -> None:
    captured = {}

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        True,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_RERANKER_ENABLED",
        False,
    )

    def fake_hybrid(
        *,
        db,
        query,
    ):
        captured["query_text"] = query.text
        return []

    monkeypatch.setattr(
        rag_module,
        "search_hybrid_chunks",
        fake_hybrid,
    )

    rag_module._retrieve_rag_hits(
        db=None,
        query=make_query(),
        query_rewriter=FakeQueryRewriter(),
    )

    assert captured["query_text"] == (
        "yearly security assessment scheduled month"
    )


def test_reranker_gets_original_question(
    monkeypatch,
) -> None:
    captured = {}

    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        True,
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

    fake_reranker = object()

    def fake_reranked(
        *,
        db,
        query,
        reranker,
        candidate_depth,
        fallback_on_error,
        reranker_query_text,
    ):
        captured["retrieval_text"] = (
            query.text
        )
        captured["reranker_text"] = (
            reranker_query_text
        )
        return []

    monkeypatch.setattr(
        rag_module,
        "search_reranked_chunks",
        fake_reranked,
    )

    original = make_query()

    rag_module._retrieve_rag_hits(
        db=None,
        query=original,
        reranker=fake_reranker,
        query_rewriter=FakeQueryRewriter(),
    )

    assert captured["retrieval_text"] == (
        "yearly security assessment scheduled month"
    )

    assert captured["reranker_text"] == (
        original.text
    )
