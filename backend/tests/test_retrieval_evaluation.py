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