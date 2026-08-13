import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.retrieval.benchmark import (
    RetrievalBenchmarkSpec,
    load_benchmark_specs,
    run_retrieval_benchmark,
)
from app.retrieval.evaluation import (
    RetrievalEvaluationCase,
)

import app.retrieval.benchmark as benchmark_module


@dataclass(frozen=True)
class FakeProviderInfo:
    provider_name: str = "fake-semantic"
    model_name: str = "fake-model"


class FakeProvider:
    info = FakeProviderInfo()


@dataclass(frozen=True)
class FakeHit:
    chunk_id: str


def test_load_benchmark_specs(
    tmp_path: Path,
) -> None:
    dataset_path = (
        tmp_path
        / "retrieval_cases.json"
    )

    dataset_path.write_text(
        json.dumps(
            {
                "version": 1,
                "cases": [
                    {
                        "query_id": "q1",
                        "query": (
                            "When is the review?"
                        ),
                        "document_filename": (
                            "policy.md"
                        ),
                        "evidence_marker": (
                            "review happens in October"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = load_benchmark_specs(
        dataset_path
    )

    assert len(specs) == 1

    assert specs[0] == (
        RetrievalBenchmarkSpec(
            query_id="q1",
            query=(
                "When is the review?"
            ),
            document_filename=(
                "policy.md"
            ),
            evidence_marker=(
                "review happens in October"
            ),
        )
    )


def test_load_benchmark_specs_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    dataset_path = (
        tmp_path
        / "duplicate.json"
    )

    case = {
        "query_id": "same",
        "query": "Question",
        "document_filename": "doc.md",
        "evidence_marker": "Evidence",
    }

    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    case,
                    dict(case),
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="query IDs",
    ):
        load_benchmark_specs(
            dataset_path
        )


def test_run_benchmark_compares_vector_and_hybrid(
    monkeypatch,
) -> None:
    cases = (
        RetrievalEvaluationCase(
            query_id="q1",
            query="first question",
            relevant_chunk_ids=(
                frozenset(
                    {"relevant-1"}
                )
            ),
        ),
        RetrievalEvaluationCase(
            query_id="q2",
            query="second question",
            relevant_chunk_ids=(
                frozenset(
                    {"relevant-2"}
                )
            ),
        ),
    )

    monkeypatch.setattr(
        benchmark_module,
        "resolve_evaluation_cases",
        lambda **kwargs: cases,
    )

    def fake_vector_search(
        **kwargs,
    ):
        query = kwargs["query"]

        assert query.top_k == 20

        if query.text == "first question":
            return [
                FakeHit("noise"),
                FakeHit("relevant-1"),
            ]

        return [
            FakeHit("noise-2"),
        ]

    def fake_hybrid_search(
        **kwargs,
    ):
        query = kwargs["query"]

        assert query.top_k == 20

        if query.text == "first question":
            return [
                FakeHit("relevant-1"),
            ]

        return [
            FakeHit("relevant-2"),
        ]

    monkeypatch.setattr(
        benchmark_module,
        "search_similar_chunks",
        fake_vector_search,
    )

    monkeypatch.setattr(
        benchmark_module,
        "search_hybrid_chunks",
        fake_hybrid_search,
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
        k=2,
        provider=FakeProvider(),
    )

    assert report.case_count == 2
    assert report.retrieval_depth == 20

    assert (
        report.vector.hit_rate_at_k
        == pytest.approx(0.5)
    )

    assert (
        report.vector.mean_recall_at_k
        == pytest.approx(0.5)
    )

    assert (
        report.vector.mrr_at_k
        == pytest.approx(0.25)
    )

    assert (
        report.hybrid.hit_rate_at_k
        == pytest.approx(1.0)
    )

    assert (
        report.hybrid.mean_recall_at_k
        == pytest.approx(1.0)
    )

    assert (
        report.hybrid.mrr_at_k
        == pytest.approx(1.0)
    )

    assert (
        report.hit_rate_delta
        == pytest.approx(0.5)
    )

    assert (
        report.recall_delta
        == pytest.approx(0.5)
    )

    assert (
        report.mrr_delta
        == pytest.approx(0.75)
    )

    assert (
        report.benchmark_label
        == "semantic retrieval benchmark"
    )
