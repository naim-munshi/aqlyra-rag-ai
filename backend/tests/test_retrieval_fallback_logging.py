import logging

import app.services.rag_answer_service as rag_module

from app.query_rewriting import (
    QueryRewriteValidationError,
)
from app.reranking import RerankerError
from app.retrieval import RetrievalQuery
from app.services.reranked_retrieval_service import (
    rerank_hits,
)


class FailingQueryRewriter:
    def rewrite(
        self,
        query: str,
    ) -> str:
        raise QueryRewriteValidationError(
            "invalid rewrite"
        )


class FailingReranker:
    def rerank(
        self,
        *,
        query,
        hits,
    ):
        raise RerankerError(
            "reranking failed"
        )


def make_query() -> RetrievalQuery:
    return RetrievalQuery(
        user_id="user-1",
        text="Which evidence is relevant?",
        top_k=5,
        chunk_roles=("content",),
    )


def test_query_rewrite_fallback_is_logged(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        True,
    )

    query = make_query()

    with caplog.at_level(
        logging.WARNING,
        logger=rag_module.__name__,
    ):
        result = (
            rag_module._rewrite_retrieval_query(
                query=query,
                query_rewriter=(
                    FailingQueryRewriter()
                ),
            )
        )

    assert result is query
    assert "query_rewrite_failed" in caplog.text
    assert (
        "fallback=original_query"
        in caplog.text
    )
    assert (
        "error_type="
        "QueryRewriteValidationError"
        in caplog.text
    )


def test_reranker_config_fallback_is_logged(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setattr(
        rag_module.settings,
        "RAG_QUERY_REWRITE_ENABLED",
        False,
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

    expected = [object()]

    def fail_factory():
        raise RerankerError(
            "invalid reranker config"
        )

    monkeypatch.setattr(
        rag_module,
        "create_configured_reranker",
        fail_factory,
    )

    monkeypatch.setattr(
        rag_module,
        "search_hybrid_chunks",
        lambda **kwargs: expected,
    )

    with caplog.at_level(
        logging.WARNING,
        logger=rag_module.__name__,
    ):
        result = rag_module._retrieve_rag_hits(
            db=None,
            query=make_query(),
        )

    assert result is expected
    assert "reranker_config_failed" in caplog.text
    assert "fallback=hybrid" in caplog.text
    assert (
        "error_type=RerankerError"
        in caplog.text
    )


def test_reranker_runtime_fallback_is_logged(
    caplog,
) -> None:
    hits = [object()]

    with caplog.at_level(logging.WARNING):
        result = rerank_hits(
            query_text="original question",
            hits=hits,
            reranker=FailingReranker(),
            fallback_on_error=True,
        )

    assert result == hits
    assert (
        "reranker_runtime_failed"
        in caplog.text
    )
    assert (
        "fallback=original_hybrid_order"
        in caplog.text
    )
    assert (
        "error_type=RerankerError"
        in caplog.text
    )


def test_reranker_error_is_not_logged_when_raised(
    caplog,
) -> None:
    hits = [object()]

    try:
        with caplog.at_level(logging.WARNING):
            rerank_hits(
                query_text="original question",
                hits=hits,
                reranker=FailingReranker(),
                fallback_on_error=False,
            )
    except RerankerError:
        pass
    else:
        raise AssertionError(
            "Expected RerankerError"
        )

    assert (
        "reranker_runtime_failed"
        not in caplog.text
    )
