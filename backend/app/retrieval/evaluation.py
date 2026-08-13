from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    query_id: str
    query: str
    relevant_chunk_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.query_id.strip():
            raise ValueError(
                "query_id cannot be empty"
            )

        if not self.query.strip():
            raise ValueError(
                "query cannot be empty"
            )

        if not self.relevant_chunk_ids:
            raise ValueError(
                "At least one relevant chunk "
                "is required"
            )

        if any(
            not chunk_id.strip()
            for chunk_id
            in self.relevant_chunk_ids
        ):
            raise ValueError(
                "Relevant chunk IDs "
                "cannot be empty"
            )


@dataclass(frozen=True, slots=True)
class RetrievalCaseMetrics:
    query_id: str
    hit_at_k: bool
    recall_at_k: float
    reciprocal_rank: float
    first_relevant_rank: int | None
    relevant_hits: tuple[str, ...]
    retrieved_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationSummary:
    k: int
    case_count: int
    hit_rate_at_k: float
    mean_recall_at_k: float
    mrr_at_k: float
    cases: tuple[RetrievalCaseMetrics, ...]


def _unique_ranked_ids(
    chunk_ids: tuple[str, ...],
) -> tuple[str, ...]:
    unique: list[str] = []
    seen: set[str] = set()

    for chunk_id in chunk_ids:
        cleaned = chunk_id.strip()

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        unique.append(cleaned)

    return tuple(unique)


def evaluate_case(
    *,
    case: RetrievalEvaluationCase,
    retrieved_chunk_ids: tuple[str, ...],
    k: int,
) -> RetrievalCaseMetrics:
    if k < 1:
        raise ValueError(
            "k must be at least 1"
        )

    ranked_ids = _unique_ranked_ids(
        retrieved_chunk_ids
    )[:k]

    relevant_hits = tuple(
        chunk_id
        for chunk_id in ranked_ids
        if chunk_id
        in case.relevant_chunk_ids
    )

    first_relevant_rank: int | None = None

    for rank, chunk_id in enumerate(
        ranked_ids,
        start=1,
    ):
        if (
            chunk_id
            in case.relevant_chunk_ids
        ):
            first_relevant_rank = rank
            break

    hit_at_k = bool(
        relevant_hits
    )

    recall_at_k = (
        len(relevant_hits)
        / len(case.relevant_chunk_ids)
    )

    reciprocal_rank = (
        1.0 / first_relevant_rank
        if first_relevant_rank is not None
        else 0.0
    )

    return RetrievalCaseMetrics(
        query_id=case.query_id,
        hit_at_k=hit_at_k,
        recall_at_k=recall_at_k,
        reciprocal_rank=reciprocal_rank,
        first_relevant_rank=(
            first_relevant_rank
        ),
        relevant_hits=relevant_hits,
        retrieved_chunk_ids=ranked_ids,
    )


def evaluate_rankings(
    *,
    cases: tuple[
        RetrievalEvaluationCase,
        ...
    ],
    rankings: dict[
        str,
        tuple[str, ...],
    ],
    k: int,
) -> RetrievalEvaluationSummary:
    if k < 1:
        raise ValueError(
            "k must be at least 1"
        )

    if not cases:
        raise ValueError(
            "At least one evaluation case "
            "is required"
        )

    query_ids = [
        case.query_id
        for case in cases
    ]

    if len(query_ids) != len(
        set(query_ids)
    ):
        raise ValueError(
            "Evaluation query IDs "
            "must be unique"
        )

    case_metrics = tuple(
        evaluate_case(
            case=case,
            retrieved_chunk_ids=(
                rankings.get(
                    case.query_id,
                    (),
                )
            ),
            k=k,
        )
        for case in cases
    )

    case_count = len(
        case_metrics
    )

    hit_rate = (
        sum(
            1
            for result in case_metrics
            if result.hit_at_k
        )
        / case_count
    )

    mean_recall = (
        sum(
            result.recall_at_k
            for result in case_metrics
        )
        / case_count
    )

    mrr = (
        sum(
            result.reciprocal_rank
            for result in case_metrics
        )
        / case_count
    )

    return RetrievalEvaluationSummary(
        k=k,
        case_count=case_count,
        hit_rate_at_k=hit_rate,
        mean_recall_at_k=mean_recall,
        mrr_at_k=mrr,
        cases=case_metrics,
    )