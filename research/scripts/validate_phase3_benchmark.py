#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "research" / "benchmark_v0.3"

ALLOWED_RETRIEVERS = {
    "LEXICAL_ONLY",
    "DENSE_ONLY",
    "AQ-LYRA_HYBRID",
    "UNION_RRF",
}

ALLOWED_POLICIES = {
    "RANDOM",
    "RELEVANCE-DEPLETED",
    "RELEVANCE-PRESERVING",
}

ALLOWED_COVERAGE_LEVELS = {
    1.00,
    0.90,
    0.75,
    0.50,
    0.25,
    0.10,
    0.00,
}

ALLOWED_ANSWERABILITY = {
    "answerable",
    "unanswerable",
    "conflict",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise ValueError(f"Missing file: {path}")

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Empty CSV: {path}")

    fieldnames = rows[0]

    if not fieldnames:
        raise ValueError(f"No CSV header: {path}")

    expected_width = len(fieldnames)

    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != expected_width:
            raise ValueError(
                f"{path.name}: non-rectangular CSV at row {row_number}; "
                f"expected {expected_width} columns, found {len(row)}"
            )

    records = [
        dict(zip(fieldnames, row))
        for row in rows[1:]
    ]

    return fieldnames, records


def require_columns(
    path: Path,
    fieldnames: list[str],
    required: set[str],
) -> None:
    missing = sorted(required - set(fieldnames))

    if missing:
        raise ValueError(
            f"{path.name}: missing required columns: "
            f"{', '.join(missing)}"
        )


def require_unique(
    path: Path,
    rows: list[dict[str, str]],
    field: str,
) -> None:
    seen: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        value = row.get(field, "").strip()

        if not value:
            raise ValueError(
                f"{path.name}: empty {field} at row {row_number}"
            )

        if value in seen:
            raise ValueError(
                f"{path.name}: duplicate {field}={value!r} "
                f"at row {row_number}"
            )

        seen.add(value)


def validate_queries(
    data_dir: Path,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    path = data_dir / "queries.csv"

    required = {
        "dataset_id",
        "query_id",
        "question",
        "question_type",
        "answerability",
    }

    fields, rows = read_csv(path)
    require_columns(path, fields, required)
    require_unique(path, rows, "query_id")

    query_map: dict[str, dict[str, str]] = {}

    for row_number, row in enumerate(rows, start=2):
        query_id = row["query_id"].strip()
        dataset_id = row["dataset_id"].strip()
        question = row["question"].strip()
        answerability = row["answerability"].strip()

        if not dataset_id:
            raise ValueError(
                f"{path.name}: empty dataset_id at row {row_number}"
            )

        if not question:
            raise ValueError(
                f"{path.name}: empty question at row {row_number}"
            )

        if answerability not in ALLOWED_ANSWERABILITY:
            raise ValueError(
                f"{path.name}: invalid answerability="
                f"{answerability!r} at row {row_number}"
            )

        query_map[query_id] = row

    return query_map, rows


def validate_documents(
    data_dir: Path,
) -> tuple[set[tuple[str, str, str]], list[dict[str, str]]]:
    path = data_dir / "documents.csv"

    required = {
        "dataset_id",
        "source_doc_id",
        "document_version",
        "source_unit_id",
        "unit_order",
        "content_hash_sha256",
        "source_type",
        "source_reference",
        "license",
        "text",
    }

    fields, rows = read_csv(path)
    require_columns(path, fields, required)

    unit_keys: set[tuple[str, str, str]] = set()

    for row_number, row in enumerate(rows, start=2):
        dataset_id = row["dataset_id"].strip()
        source_doc_id = row["source_doc_id"].strip()
        document_version = row["document_version"].strip()
        source_unit_id = row["source_unit_id"].strip()
        text = row["text"].strip()

        if not all(
            [dataset_id, source_doc_id, document_version, source_unit_id]
        ):
            raise ValueError(
                f"{path.name}: missing document/unit identifier "
                f"at row {row_number}"
            )

        if not text:
            raise ValueError(
                f"{path.name}: empty text at row {row_number}"
            )

        key = (
            dataset_id,
            source_doc_id,
            source_unit_id,
        )

        if key in unit_keys:
            raise ValueError(
                f"{path.name}: duplicate retrieval unit {key!r} "
                f"at row {row_number}"
            )

        unit_keys.add(key)

    return unit_keys, rows


def validate_qrels(
    data_dir: Path,
    query_map: dict[str, dict[str, str]],
    document_units: set[tuple[str, str, str]],
) -> list[dict[str, str]]:
    path = data_dir / "qrels.csv"

    required = {
        "dataset_id",
        "query_id",
        "source_doc_id",
        "document_version",
        "source_unit_id",
        "relevance_grade",
    }

    fields, rows = read_csv(path)
    require_columns(path, fields, required)

    seen: set[tuple[str, str, str, str]] = set()
    positive_counts: dict[str, int] = {qid: 0 for qid in query_map}
    conflict_positive_counts: dict[str, int] = {qid: 0 for qid in query_map}

    for row_number, row in enumerate(rows, start=2):
        dataset_id = row["dataset_id"].strip()
        query_id = row["query_id"].strip()
        source_doc_id = row["source_doc_id"].strip()
        source_unit_id = row["source_unit_id"].strip()

        if query_id not in query_map:
            raise ValueError(
                f"{path.name}: unknown query_id={query_id!r} "
                f"at row {row_number}"
            )

        query_dataset = query_map[query_id]["dataset_id"].strip()

        if dataset_id != query_dataset:
            raise ValueError(
                f"{path.name}: dataset mismatch for query_id={query_id!r} "
                f"at row {row_number}"
            )

        unit_key = (
            dataset_id,
            source_doc_id,
            source_unit_id,
        )

        if unit_key not in document_units:
            raise ValueError(
                f"{path.name}: qrel references unknown retrieval unit "
                f"{unit_key!r} at row {row_number}"
            )

        try:
            grade = int(row["relevance_grade"])
        except ValueError as exc:
            raise ValueError(
                f"{path.name}: invalid relevance_grade "
                f"at row {row_number}"
            ) from exc

        if grade < 0:
            raise ValueError(
                f"{path.name}: negative relevance_grade "
                f"at row {row_number}"
            )

        key = (
            dataset_id,
            query_id,
            source_doc_id,
            source_unit_id,
        )

        if key in seen:
            raise ValueError(
                f"{path.name}: duplicate qrel {key!r} "
                f"at row {row_number}"
            )

        seen.add(key)

        if grade > 0:
            positive_counts[query_id] += 1

            conflict_flag = row.get(
                "conflicting_unit_flag",
                ""
            ).strip().lower()

            if conflict_flag == "true":
                conflict_positive_counts[query_id] += 1
            elif conflict_flag not in {"false", ""}:
                raise ValueError(
                    f"{path.name}: invalid conflicting_unit_flag="
                    f"{conflict_flag!r} at row {row_number}"
                )

    for query_id, query in query_map.items():
        answerability = query["answerability"].strip()
        positive = positive_counts[query_id]

        if answerability == "answerable" and positive == 0:
            raise ValueError(
                f"queries.csv: answerable query {query_id!r} "
                f"has no positive qrel"
            )

        if answerability == "unanswerable" and positive > 0:
            raise ValueError(
                f"queries.csv: unanswerable query {query_id!r} "
                f"has positive qrels"
            )

        if answerability == "conflict":
            conflict_group_id = query.get(
                "conflict_group_id",
                ""
            ).strip()
            resolution_rule = query.get(
                "resolution_rule",
                ""
            ).strip()

            if positive < 2:
                raise ValueError(
                    f"queries.csv: conflict query {query_id!r} "
                    f"requires at least two positive qrels"
                )

            if conflict_positive_counts[query_id] < 2:
                raise ValueError(
                    f"qrels.csv: conflict query {query_id!r} "
                    f"requires at least two conflicting positive qrels"
                )

            if not conflict_group_id:
                raise ValueError(
                    f"queries.csv: conflict query {query_id!r} "
                    f"requires conflict_group_id"
                )

            if not resolution_rule:
                raise ValueError(
                    f"queries.csv: conflict query {query_id!r} "
                    f"requires resolution_rule"
                )

    return rows


def validate_run_schema_definition() -> None:
    path = BENCH / "PHASE3_RUN_SCHEMA_v0.3.csv"

    fields, rows = read_csv(path)

    require_columns(
        path,
        fields,
        {"field", "type", "required", "description"},
    )

    names = [row["field"].strip() for row in rows]

    if len(names) != len(set(names)):
        raise ValueError(
            f"{path.name}: duplicate schema field names"
        )

    required = {
        "run_id",
        "benchmark_version",
        "dataset_id",
        "query_id",
        "retriever_condition",
        "coverage_target",
        "coverage_achieved",
        "coverage_policy",
        "coverage_seed",
        "eligible_unit_count",
        "compatible_unit_count",
        "embedding_provider",
        "embedding_model",
        "embedding_dimension",
        "top_k",
        "authorization_scope_id",
        "unauthorized_retrieval_count",
        "git_commit",
        "runtime_environment",
        "run_timestamp",
    }

    missing = sorted(required - set(names))

    if missing:
        raise ValueError(
            f"{path.name}: missing run fields: "
            f"{', '.join(missing)}"
        )


def validate_masking_matrix() -> None:
    path = BENCH / "PHASE3_MASKING_MATRIX_v0.3.csv"

    fields, rows = read_csv(path)

    require_columns(
        path,
        fields,
        {"mask_id", "coverage", "policy", "seeds", "mask_scope", "role"},
    )

    require_unique(path, rows, "mask_id")

    for row_number, row in enumerate(rows, start=2):
        try:
            coverage = float(row["coverage"])
        except ValueError as exc:
            raise ValueError(
                f"{path.name}: invalid coverage at row {row_number}"
            ) from exc

        if coverage not in ALLOWED_COVERAGE_LEVELS:
            raise ValueError(
                f"{path.name}: unsupported coverage={coverage} "
                f"at row {row_number}"
            )

        policy = row["policy"].strip()

        if policy not in ALLOWED_POLICIES:
            raise ValueError(
                f"{path.name}: invalid policy={policy!r} "
                f"at row {row_number}"
            )


def validate_run_files_if_present(data_dir: Path) -> None:
    run_files = sorted((BENCH / "runs").glob("*.csv"))

    if not run_files:
        print("RUN FILES: none yet (expected during Phase 3 construction)")
        return

    required = {
        "run_id",
        "benchmark_version",
        "dataset_id",
        "query_id",
        "retriever_condition",
        "coverage_target",
        "coverage_achieved",
        "coverage_policy",
        "coverage_seed",
        "eligible_unit_count",
        "compatible_unit_count",
        "unauthorized_retrieval_count",
    }

    for path in run_files:
        fields, rows = read_csv(path)
        require_columns(path, fields, required)

        for row_number, row in enumerate(rows, start=2):
            condition = row["retriever_condition"].strip()

            if condition not in ALLOWED_RETRIEVERS:
                raise ValueError(
                    f"{path.name}: invalid retriever_condition="
                    f"{condition!r} at row {row_number}"
                )

            target = float(row["coverage_target"])
            achieved = float(row["coverage_achieved"])

            if not 0.0 <= target <= 1.0:
                raise ValueError(
                    f"{path.name}: coverage_target outside [0,1] "
                    f"at row {row_number}"
                )

            if not 0.0 <= achieved <= 1.0:
                raise ValueError(
                    f"{path.name}: coverage_achieved outside [0,1] "
                    f"at row {row_number}"
                )

            policy = row["coverage_policy"].strip()

            if policy not in ALLOWED_POLICIES:
                raise ValueError(
                    f"{path.name}: invalid coverage_policy="
                    f"{policy!r} at row {row_number}"
                )

            eligible = int(row["eligible_unit_count"])
            compatible = int(row["compatible_unit_count"])
            unauthorized = int(row["unauthorized_retrieval_count"])

            if eligible < 0 or compatible < 0:
                raise ValueError(
                    f"{path.name}: negative unit count "
                    f"at row {row_number}"
                )

            if compatible > eligible:
                raise ValueError(
                    f"{path.name}: compatible > eligible "
                    f"at row {row_number}"
                )

            if eligible == 0 and compatible != 0:
                raise ValueError(
                    f"{path.name}: compatible units exist with "
                    f"zero eligible units at row {row_number}"
                )

            if unauthorized != 0:
                raise ValueError(
                    f"{path.name}: SECURITY INVARIANT VIOLATION: "
                    f"unauthorized_retrieval_count={unauthorized}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Aqlyra Phase 3 benchmark data."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=BENCH / "data",
        help="Directory containing documents.csv, queries.csv, qrels.csv",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()

    print("=== Aqlyra Phase 3 Benchmark Validator ===")
    print(f"Benchmark root: {BENCH}")
    print(f"Data directory: {data_dir}")

    validate_run_schema_definition()
    print("RUN SCHEMA: PASS")

    validate_masking_matrix()
    print("MASKING MATRIX: PASS")

    query_map, queries = validate_queries(data_dir)
    print(f"QUERIES: PASS ({len(queries)} rows)")

    document_units, documents = validate_documents(data_dir)
    print(f"DOCUMENTS: PASS ({len(documents)} rows)")

    qrels = validate_qrels(
        data_dir,
        query_map,
        document_units,
    )
    print(f"QRELS: PASS ({len(qrels)} rows)")

    validate_run_files_if_present(data_dir)

    print("\nPHASE 3 VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"\nPHASE 3 VALIDATION: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1)
