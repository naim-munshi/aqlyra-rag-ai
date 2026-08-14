import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.database.connection import (
    SessionLocal,
)
from app.config.settings import settings
from app.llms import (
    create_llm_provider,
)
from app.query_rewriting import (
    IdentityQueryRewriter,
    QueryRewriter,
    create_configured_query_rewriter,
)
from app.reranking.llm_provider import (
    RERANKER_TEXT_FORMAT,
)
from app.reranking import (
    IdentityReranker,
    LLMReranker,
    RerankerProvider,
)
from app.retrieval.benchmark import (
    load_benchmark_specs,
    run_retrieval_benchmark,
)


def create_reranker(
    name: str,
) -> RerankerProvider | None:
    if name == "none":
        return None

    if name == "identity":
        return IdentityReranker()

    if name == "llm":
        api_key = ""

        if settings.LLM_PROVIDER == "groq":
            api_key = settings.GROQ_API_KEY
        elif settings.LLM_PROVIDER == "openai":
            api_key = settings.OPENAI_API_KEY

        provider = create_llm_provider(
            provider_name=(
                settings.LLM_PROVIDER
            ),
            model_name=settings.LLM_MODEL,
            api_key=api_key,
            max_output_tokens=1_024,
            timeout_seconds=(
                settings.LLM_TIMEOUT_SECONDS
            ),
            max_retries=(
                settings.LLM_MAX_RETRIES
            ),
            reasoning_effort="low",
            text_format=(
                RERANKER_TEXT_FORMAT
            ),
        )

        return LLMReranker(
            provider=provider
        )

    raise ValueError(
        f"Unsupported reranker: {name}"
    )


def create_query_rewriter(
    name: str,
) -> QueryRewriter | None:
    if name == "none":
        return None

    if name == "identity":
        return IdentityQueryRewriter()

    if name == "llm":
        return create_configured_query_rewriter()

    raise ValueError(
        f"Unsupported query rewriter: {name}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Aqlyra vector and hybrid "
            "retrieval on labeled cases."
        )
    )

    parser.add_argument(
        "--user-id",
        required=True,
        help=(
            "Owner of the ready documents "
            "used by the benchmark."
        ),
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help=(
            "Path to the benchmark JSON "
            "dataset."
        ),
    )

    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Evaluate top-K retrieval.",
    )

    parser.add_argument(
        "--retrieval-depth",
        type=int,
        default=20,
        help=(
            "Fixed retrieval depth used before "
            "calculating metrics at K."
        ),
    )

    parser.add_argument(
        "--query-rewriter",
        choices=(
            "none",
            "identity",
            "llm",
        ),
        default="none",
        help=(
            "Optional retrieval query rewriter. "
            "'llm' uses the configured LLM "
            "provider."
        ),
    )

    parser.add_argument(
        "--reranker",
        choices=(
            "none",
            "identity",
            "llm",
        ),
        default="none",
        help=(
            "Optional candidate reranker. "
            "'llm' uses the configured "
            "LLM provider."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional JSON report output path."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    specs = load_benchmark_specs(
        args.dataset
    )

    reranker = create_reranker(
        args.reranker
    )

    query_rewriter = create_query_rewriter(
        args.query_rewriter
    )

    with SessionLocal() as db:
        report = run_retrieval_benchmark(
            db=db,
            user_id=args.user_id,
            specs=specs,
            k=args.k,
            retrieval_depth=(
                args.retrieval_depth
            ),
            reranker=reranker,
            query_rewriter=query_rewriter,
        )

    print()
    print("Aqlyra Retrieval Benchmark")
    print("=" * 44)

    print(
        "Provider:",
        report.provider_name,
    )

    print(
        "Model:",
        report.model_name,
    )

    print(
        "Label:",
        report.benchmark_label,
    )

    print(
        f"Cases: {report.case_count}"
    )

    print(
        f"K: {report.k}"
    )

    print(
        "Retrieval depth:",
        report.retrieval_depth,
    )

    if (
        report.query_rewriter_provider_name
        is not None
    ):
        print(
            "Query rewriter:",
            report.query_rewriter_provider_name,
            "/",
            report.query_rewriter_model_name,
        )

    if report.reranked is not None:
        print(
            "Reranker:",
            report.reranker_provider_name,
            "/",
            report.reranker_model_name,
        )

    print()

    if report.reranked is None:
        print(
            "Metric".ljust(18),
            "Vector".rjust(10),
            "Hybrid".rjust(10),
            "V→H".rjust(10),
        )

        print("-" * 51)

        rows = (
            (
                "Hit Rate@K",
                report.vector.hit_rate_at_k,
                report.hybrid.hit_rate_at_k,
                report.hit_rate_delta,
            ),
            (
                "Recall@K",
                report.vector.mean_recall_at_k,
                report.hybrid.mean_recall_at_k,
                report.recall_delta,
            ),
            (
                "MRR@K",
                report.vector.mrr_at_k,
                report.hybrid.mrr_at_k,
                report.mrr_delta,
            ),
        )

        for name, vector, hybrid, delta in rows:
            print(
                name.ljust(18),
                f"{vector:.3f}".rjust(10),
                f"{hybrid:.3f}".rjust(10),
                f"{delta:+.3f}".rjust(10),
            )

    else:
        print(
            "Metric".ljust(18),
            "Vector".rjust(10),
            "Hybrid".rjust(10),
            "Reranked".rjust(10),
            "H→R".rjust(10),
        )

        print("-" * 61)

        rows = (
            (
                "Hit Rate@K",
                report.vector.hit_rate_at_k,
                report.hybrid.hit_rate_at_k,
                report.reranked.hit_rate_at_k,
                report.rerank_hit_rate_delta,
            ),
            (
                "Recall@K",
                report.vector.mean_recall_at_k,
                report.hybrid.mean_recall_at_k,
                report.reranked.mean_recall_at_k,
                report.rerank_recall_delta,
            ),
            (
                "MRR@K",
                report.vector.mrr_at_k,
                report.hybrid.mrr_at_k,
                report.reranked.mrr_at_k,
                report.rerank_mrr_delta,
            ),
        )

        for (
            name,
            vector,
            hybrid,
            reranked,
            delta,
        ) in rows:
            print(
                name.ljust(18),
                f"{vector:.3f}".rjust(10),
                f"{hybrid:.3f}".rjust(10),
                f"{reranked:.3f}".rjust(10),
                f"{delta:+.3f}".rjust(10),
            )

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                asdict(report),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        print()
        print(
            "JSON report:",
            args.output,
        )


if __name__ == "__main__":
    main()
