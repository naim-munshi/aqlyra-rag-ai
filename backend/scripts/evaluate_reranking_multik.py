import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.config.settings import settings
from app.database.connection import SessionLocal
from app.llms import create_llm_provider
from app.reranking import LLMReranker
from app.reranking.llm_provider import (
    RERANKER_TEXT_FORMAT,
)
from app.retrieval.benchmark import (
    load_benchmark_specs,
)
from app.retrieval.reranking_benchmark import (
    run_reranking_benchmark_once,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one-pass Aqlyra LLM reranking "
            "and evaluate several K values."
        )
    )

    parser.add_argument(
        "--user-id",
        required=True,
    )

    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--retrieval-depth",
        type=int,
        default=15,
    )

    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=45.0,
        help=(
            "Delay between LLM reranker calls "
            "for provider rate-limit safety."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    return parser.parse_args()


def create_reranker() -> LLMReranker:
    api_key = ""

    if settings.LLM_PROVIDER == "groq":
        api_key = settings.GROQ_API_KEY
    elif settings.LLM_PROVIDER == "openai":
        api_key = settings.OPENAI_API_KEY

    provider = create_llm_provider(
        provider_name=settings.LLM_PROVIDER,
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
        provider=provider,
        max_candidate_chars=900,
    )


def main() -> None:
    args = parse_args()

    specs = load_benchmark_specs(
        args.dataset
    )

    reranker = create_reranker()

    with SessionLocal() as db:
        report = run_reranking_benchmark_once(
            db=db,
            user_id=args.user_id,
            specs=specs,
            reranker=reranker,
            ks=(1, 3, 5),
            retrieval_depth=(
                args.retrieval_depth
            ),
            delay_seconds=(
                args.delay_seconds
            ),
        )

    print()
    print("Aqlyra Multi-K Reranking Benchmark")
    print("=" * 72)
    print(
        "Embedding:",
        report.provider_name,
        "/",
        report.model_name,
    )
    print(
        "Reranker:",
        report.reranker_provider_name,
        "/",
        report.reranker_model_name,
    )
    print(
        "Cases:",
        report.case_count,
    )
    print(
        "Candidate depth:",
        report.retrieval_depth,
    )
    print(
        "Label:",
        report.benchmark_label,
    )

    for result in report.results:
        print()
        print(f"@{result.k}")
        print("-" * 72)

        print(
            "Metric".ljust(14),
            "Vector".rjust(10),
            "Hybrid".rjust(10),
            "Reranked".rjust(10),
            "H→R".rjust(10),
        )

        rows = (
            (
                "Hit Rate",
                result.vector.hit_rate_at_k,
                result.hybrid.hit_rate_at_k,
                result.reranked.hit_rate_at_k,
                result.rerank_hit_rate_delta,
            ),
            (
                "Recall",
                result.vector.mean_recall_at_k,
                result.hybrid.mean_recall_at_k,
                result.reranked.mean_recall_at_k,
                result.rerank_recall_delta,
            ),
            (
                "MRR",
                result.vector.mrr_at_k,
                result.hybrid.mrr_at_k,
                result.reranked.mrr_at_k,
                result.rerank_mrr_delta,
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
                name.ljust(14),
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
