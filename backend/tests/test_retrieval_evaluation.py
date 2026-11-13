import pytest

from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
    evaluate_case,
    evaluate_rankings,
)


def test_evaluate_case_calculates_metrics(
) -> None:
    case = RetrievalEvaluationCase(
        query_id="security-review",
        query=(
            "When does the annual "
            "security review happen?"
        ),
        relevant_chunk_ids=frozenset(
            {
                "chunk-security",
                "chunk-calendar",
            }
        ),
    )

    result = evaluate_case(
        case=case,
        retrieved_chunk_ids=(
            "chunk-noise",
            "chunk-security",
            "chunk-other",
            "chunk-calendar",
        ),
        k=4,
    )

    assert result.hit_at_k is True

    assert (
        result.recall_at_k
        == pytest.approx(1.0)
    )

    assert (
        result.first_relevant_rank
        == 2
    )

    assert (
        result.reciprocal_rank
        == pytest.approx(0.5)
    )


def test_evaluate_case_handles_miss(
) -> None:
    case = RetrievalEvaluationCase(
        query_id="backup-policy",
        query="When are backups verified?",
        relevant_chunk_ids=frozenset(
            {"chunk-backup"}
        ),
    )

    result = evaluate_case(
        case=case,
        retrieved_chunk_ids=(
            "chunk-a",
            "chunk-b",
        ),
        k=2,
    )

    assert result.hit_at_k is False
    assert result.recall_at_k == 0.0
    assert result.reciprocal_rank == 0.0
    assert (
        result.first_relevant_rank
        is None
    )


def test_duplicate_results_do_not_change_rank(
) -> None:
    case = RetrievalEvaluationCase(
        query_id="duplicate-test",
        query="Find the target",
        relevant_chunk_ids=frozenset(
            {"target"}
        ),
    )

    result = evaluate_case(
        case=case,
        retrieved_chunk_ids=(
            "noise",
            "target",
            "target",
        ),
        k=3,
    )

    assert (
        result.first_relevant_rank
        == 2
    )

    assert result.relevant_hits == (
        "target",
    )


def test_evaluate_rankings_builds_summary(
) -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="q1",
            query="Question one",
            relevant_chunk_ids=frozenset(
                {"target-1"}
            ),
        ),
        RetrievalEvaluationCase(
            query_id="q2",
            query="Question two",
            relevant_chunk_ids=frozenset(
                {"target-2"}
            ),
        ),
    )

    summary = evaluate_rankings(
        cases=cases,
        rankings={
            "q1": (
                "noise",
                "target-1",
            ),
            "q2": (
                "noise-a",
                "noise-b",
            ),
        },
        k=2,
    )

    assert summary.case_count == 2

    assert (
        summary.hit_rate_at_k
        == pytest.approx(0.5)
    )

    assert (
        summary.mean_recall_at_k
        == pytest.approx(0.5)
    )

    assert (
        summary.mrr_at_k
        == pytest.approx(0.25)
    )


def test_evaluation_rejects_invalid_input(
) -> None:
    with pytest.raises(ValueError):
        RetrievalEvaluationCase(
            query_id="",
            query="Valid query",
            relevant_chunk_ids=frozenset(
                {"chunk-1"}
            ),
        )

    with pytest.raises(ValueError):
        evaluate_rankings(
            cases=(),
            rankings={},
            k=5,
        )

def test_ndcg_at_k_rewards_correct_relevance_order() -> None:
    case = RetrievalEvaluationCase(
        query_id="multilingual-benchmark",
        query="日本語のポリシーは？",
        relevant_chunk_ids=frozenset({"a", "b"}),
    )
    ideal = evaluate_case(
        case=case,
        retrieved_chunk_ids=("a", "b", "noise"),
        k=3,
    )
    delayed = evaluate_case(
        case=case,
        retrieved_chunk_ids=("noise", "a", "b"),
        k=3,
    )
    assert ideal.ndcg_at_k == pytest.approx(1.0)
    assert 0.0 < delayed.ndcg_at_k < ideal.ndcg_at_k


def test_ndcg_is_bounded_and_ignores_duplicate_retrieval_ids() -> None:
    case = RetrievalEvaluationCase(
        query_id="dedup", query="find passage",
        relevant_chunk_ids=frozenset({"target"}),
    )
    answer = evaluate_case(
        case=case,
        retrieved_chunk_ids=("noise", "target", "target", "target"),
        k=3,
    )
    assert answer.ndcg_at_k == pytest.approx(1.0 / __import__("math").log2(3))
    assert answer.retrieved_chunk_ids == ("noise", "target")


def test_mean_ndcg_handles_hits_and_abstention_misses() -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="one", query="First query",
            relevant_chunk_ids=frozenset({"target"}),
        ),
        RetrievalEvaluationCase(
            query_id="two", query="Second query",
            relevant_chunk_ids=frozenset({"unseen"}),
        ),
    )
    report = evaluate_rankings(
        cases=cases,
        rankings={"one": ("target",), "two": ("noise",)},
        k=3,
    )
    assert report.mean_ndcg_at_k == pytest.approx(0.5)
    assert report.cases[1].ndcg_at_k == 0.0


def test_precision_at_k_counts_missing_slots_and_deduplicates_ids() -> None:
    case = RetrievalEvaluationCase(
        query_id="precision-test",
        query="Find two relevant chunks",
        relevant_chunk_ids=frozenset({"a", "b"}),
    )
    result = evaluate_case(
        case=case,
        retrieved_chunk_ids=("a", "a", "noise", "b"),
        k=4,
    )
    assert result.retrieved_chunk_ids == ("a", "noise", "b")
    assert result.precision_at_k == pytest.approx(2 / 4)
    assert result.recall_at_k == pytest.approx(1.0)
    assert result.ndcg_at_k <= 1.0

    # Do not inflate precision by dividing by the 1 returned candidate.
    sparse = evaluate_case(
        case=case,
        retrieved_chunk_ids=("a",),
        k=4,
    )
    assert sparse.precision_at_k == pytest.approx(0.25)
    assert sparse.recall_at_k == pytest.approx(0.5)

    empty = evaluate_case(
        case=case,
        retrieved_chunk_ids=(),
        k=4,
    )
    assert empty.precision_at_k == 0.0
    assert empty.hit_at_k is False


def test_mean_precision_macro_average_includes_misses() -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="p1",
            query="First",
            relevant_chunk_ids=frozenset({"a"}),
        ),
        RetrievalEvaluationCase(
            query_id="p2",
            query="Second",
            relevant_chunk_ids=frozenset({"b"}),
        ),
    )
    summary = evaluate_rankings(
        cases=cases,
        rankings={"p1": ("a",), "p2": ()},
        k=2,
    )
    # First has Precision@2 = 1/2, second = 0/2.
    assert summary.mean_precision_at_k == pytest.approx(0.25)
    assert summary.cases[0].precision_at_k == pytest.approx(0.5)
    assert summary.cases[1].precision_at_k == 0.0
    assert summary.hit_rate_at_k == pytest.approx(0.5)
