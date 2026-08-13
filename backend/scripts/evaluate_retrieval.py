import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.database.connection import (
    SessionLocal,
)
from app.retrieval.benchmark import (
    load_benchmark_specs,
    run_retrieval_benchmark,
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

    with SessionLocal() as db:
        report = run_retrieval_benchmark(
            db=db,
            user_id=args.user_id,
            specs=specs,
            k=args.k,
            retrieval_depth=(
                args.retrieval_depth
            ),
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

    print()

    print(
        "Metric".ljust(18),
        "Vector".rjust(10),
        "Hybrid".rjust(10),
        "Delta".rjust(10),
    )

    print("-" * 51)

    print(
        "Hit Rate@K".ljust(18),
        f"{report.vector.hit_rate_at_k:.3f}"
        .rjust(10),
        f"{report.hybrid.hit_rate_at_k:.3f}"
        .rjust(10),
        f"{report.hit_rate_delta:+.3f}"
        .rjust(10),
    )

    print(
        "Recall@K".ljust(18),
        f"{report.vector.mean_recall_at_k:.3f}"
        .rjust(10),
        f"{report.hybrid.mean_recall_at_k:.3f}"
        .rjust(10),
        f"{report.recall_delta:+.3f}"
        .rjust(10),
    )

    print(
        "MRR@K".ljust(18),
        f"{report.vector.mrr_at_k:.3f}"
        .rjust(10),
        f"{report.hybrid.mrr_at_k:.3f}"
        .rjust(10),
        f"{report.mrr_delta:+.3f}"
        .rjust(10),
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
