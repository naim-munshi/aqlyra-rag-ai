#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research" / "benchmark_v0.3" / "data" / "tier_a_v0.3.1"

EXPECTED_DOCS = 48
EXPECTED_UNITS_PER_DOC = 6
EXPECTED_QUERIES = 240
EXPECTED_QRELS = 288

EXPECTED_ANSWERABILITY = {
    "answerable": 192,
    "unanswerable": 24,
    "conflict": 24,
}

EXPECTED_TYPES = {
    "lexical-anchor",
    "semantic-paraphrase",
    "entity+attribute",
    "multi-hop",
    "distractor-heavy",
}

EXPECTED_OVERLAP = {
    "low",
    "moderate",
    "high",
}

BANNED_QUERY_PATTERNS = [
    r"TIERA_",
    r"_U\d+",
    r"coverage",
    r"mask",
    r"RRF",
    r"LEXICAL_ONLY",
    r"DENSE_ONLY",
    r"AQ-LYRA",
    r"UNION_RRF",
]

QUERY_ID_PATTERN = re.compile(r"^TIERA_Q\d{3}$")
DOC_ID_PATTERN = re.compile(r"^TIERA_\d{3}$")
UNIT_ID_PATTERN = re.compile(r"^TIERA_\d{3}_U\d{2}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise ValueError(f"Missing file: {path}")

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Empty CSV: {path}")

    header = rows[0]

    if not header or len(header) != len(set(header)):
        raise ValueError(f"Invalid or duplicate CSV header: {path}")

    width = len(header)

    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) != width:
            raise ValueError(
                f"{path.name}: row {line_no} has {len(row)} columns; "
                f"expected {width}"
            )

    return header, [
        dict(zip(header, row))
        for row in rows[1:]
    ]


def require_columns(
    path: Path,
    fields: list[str],
    required: set[str],
) -> None:
    missing = sorted(required - set(fields))

    if missing:
        raise ValueError(
            f"{path.name}: missing columns: {', '.join(missing)}"
        )


def load_documents():
    path = DATA / "documents.csv"

    fields, rows = read_csv(path)

    require_columns(
        path,
        fields,
        {
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
        },
    )

    units = {}
    docs = defaultdict(list)

    for line_no, row in enumerate(rows, start=2):
        doc_id = row["source_doc_id"].strip()
        unit_id = row["source_unit_id"].strip()
        text = row["text"]

        if not DOC_ID_PATTERN.match(doc_id):
            raise ValueError(
                f"Invalid source_doc_id={doc_id!r} at row {line_no}"
            )

        if not UNIT_ID_PATTERN.match(unit_id):
            raise ValueError(
                f"Invalid source_unit_id={unit_id!r} at row {line_no}"
            )

        try:
            unit_order = int(row["unit_order"])
        except ValueError as exc:
            raise ValueError(
                f"Invalid unit_order at row {line_no}"
            ) from exc

        if unit_order not in range(1, EXPECTED_UNITS_PER_DOC + 1):
            raise ValueError(
                f"{unit_id}: invalid unit_order={unit_order}"
            )

        expected_hash = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

        if row["content_hash_sha256"] != expected_hash:
            raise ValueError(
                f"{unit_id}: SHA-256 mismatch"
            )

        if row["source_type"] != "synthetic":
            raise ValueError(
                f"{doc_id}: Tier A must use synthetic source_type"
            )

        if not row["source_reference"].strip():
            raise ValueError(
                f"{unit_id}: missing source_reference"
            )

        if not row["license"].strip():
            raise ValueError(
                f"{unit_id}: missing license declaration"
            )

        key = (doc_id, unit_id)

        if key in units:
            raise ValueError(
                f"Duplicate retrieval unit: {key}"
            )

        units[key] = row
        docs[doc_id].append(row)

    if len(docs) != EXPECTED_DOCS:
        raise ValueError(
            f"Expected {EXPECTED_DOCS} documents; found {len(docs)}"
        )

    for doc_id, doc_units in docs.items():
        if len(doc_units) != EXPECTED_UNITS_PER_DOC:
            raise ValueError(
                f"{doc_id}: expected {EXPECTED_UNITS_PER_DOC} units; "
                f"found {len(doc_units)}"
            )

        orders = sorted(
            int(row["unit_order"])
            for row in doc_units
        )

        if orders != list(range(1, 7)):
            raise ValueError(
                f"{doc_id}: unit_order sequence is {orders}"
            )

    return units, docs, rows


def load_queries():
    path = DATA / "queries.csv"

    fields, rows = read_csv(path)

    require_columns(
        path,
        fields,
        {
            "dataset_id",
            "query_id",
            "primary_source_doc_id",
            "question",
            "question_type",
            "answerability",
            "gold_answer",
            "scope_id",
            "conflict_group_id",
            "resolution_rule",
            "gold_evidence_count",
            "distractor_unit_count",
            "lexical_overlap_bucket",
            "requires_multi_hop",
            "review_status",
            "annotation_notes",
        },
    )

    query_map = {}

    for line_no, row in enumerate(rows, start=2):
        query_id = row["query_id"].strip()
        doc_id = row["primary_source_doc_id"].strip()
        question = row["question"].strip()
        qtype = row["question_type"].strip()
        answerability = row["answerability"].strip()

        if not QUERY_ID_PATTERN.match(query_id):
            raise ValueError(
                f"Invalid query_id={query_id!r} at row {line_no}"
            )

        if query_id in query_map:
            raise ValueError(
                f"Duplicate query_id={query_id}"
            )

        if not question:
            raise ValueError(
                f"{query_id}: empty question"
            )

        if qtype not in EXPECTED_TYPES:
            raise ValueError(
                f"{query_id}: invalid question_type={qtype!r}"
            )

        if answerability not in EXPECTED_ANSWERABILITY:
            raise ValueError(
                f"{query_id}: invalid answerability={answerability!r}"
            )

        if row["lexical_overlap_bucket"] not in EXPECTED_OVERLAP:
            raise ValueError(
                f"{query_id}: invalid lexical overlap bucket"
            )

        if row["review_status"] not in {
            "draft",
            "reviewed",
            "frozen",
        }:
            raise ValueError(
                f"{query_id}: invalid review_status"
            )

        for pattern in BANNED_QUERY_PATTERNS:
            if re.search(pattern, question, flags=re.IGNORECASE):
                raise ValueError(
                    f"{query_id}: query leakage detected by pattern={pattern!r}"
                )

        try:
            gold_count = int(row["gold_evidence_count"])
            distractor_count = int(row["distractor_unit_count"])
        except ValueError as exc:
            raise ValueError(
                f"{query_id}: invalid evidence/distractor count"
            ) from exc

        if gold_count < 0:
            raise ValueError(
                f"{query_id}: negative gold_evidence_count"
            )

        if distractor_count < 0:
            raise ValueError(
                f"{query_id}: negative distractor_unit_count"
            )

        if row["requires_multi_hop"].lower() not in {
            "true",
            "false",
        }:
            raise ValueError(
                f"{query_id}: invalid requires_multi_hop"
            )

        if answerability == "unanswerable":
            if row["gold_answer"].strip():
                raise ValueError(
                    f"{query_id}: unanswerable query has gold_answer"
                )

            if gold_count != 0:
                raise ValueError(
                    f"{query_id}: unanswerable query must have 0 gold evidence"
                )

        elif answerability == "answerable":
            if not row["gold_answer"].strip():
                raise ValueError(
                    f"{query_id}: answerable query missing gold_answer"
                )

            if gold_count < 1:
                raise ValueError(
                    f"{query_id}: answerable query needs gold evidence"
                )

        elif answerability == "conflict":
            if not row["conflict_group_id"].strip():
                raise ValueError(
                    f"{query_id}: conflict query missing conflict_group_id"
                )

            if not row["resolution_rule"].strip():
                raise ValueError(
                    f"{query_id}: conflict query missing resolution_rule"
                )

            if not row["gold_answer"].strip():
                raise ValueError(
                    f"{query_id}: conflict query missing explicit response target"
                )

            if gold_count < 2:
                raise ValueError(
                    f"{query_id}: conflict query needs >=2 evidence units"
                )

        query_map[query_id] = row

    if len(rows) != EXPECTED_QUERIES:
        raise ValueError(
            f"Expected {EXPECTED_QUERIES} queries; found {len(rows)}"
        )

    counts = Counter(
        row["answerability"]
        for row in rows
    )

    if dict(counts) != EXPECTED_ANSWERABILITY:
        raise ValueError(
            f"Unexpected answerability distribution: {dict(counts)}"
        )

    type_counts = Counter(
        row["question_type"]
        for row in rows
    )

    if dict(type_counts) != {
        "lexical-anchor": 48,
        "semantic-paraphrase": 48,
        "entity+attribute": 48,
        "multi-hop": 48,
        "distractor-heavy": 48,
    }:
        raise ValueError(
            f"Unexpected question-type distribution: {dict(type_counts)}"
        )

    per_document = defaultdict(list)

    for row in rows:
        per_document[
            row["primary_source_doc_id"]
        ].append(row)

    if len(per_document) != EXPECTED_DOCS:
        raise ValueError(
            "Queries do not cover exactly 48 source documents"
        )

    for doc_id, doc_queries in per_document.items():
        if len(doc_queries) != 5:
            raise ValueError(
                f"{doc_id}: expected 5 queries; found {len(doc_queries)}"
            )

        type_set = {
            row["question_type"]
            for row in doc_queries
        }

        if type_set != EXPECTED_TYPES:
            raise ValueError(
                f"{doc_id}: incorrect query-type allocation: {type_set}"
            )

    return query_map, rows


def load_qrels(query_map, document_units):
    path = DATA / "qrels.csv"

    fields, rows = read_csv(path)

    require_columns(
        path,
        fields,
        {
            "dataset_id",
            "query_id",
            "source_doc_id",
            "document_version",
            "source_unit_id",
            "relevance_grade",
            "gold_evidence_span",
            "conflicting_unit_flag",
            "conflict_group_id",
            "annotation_notes",
        },
    )

    if len(rows) != EXPECTED_QRELS:
        raise ValueError(
            f"Expected {EXPECTED_QRELS} qrels; found {len(rows)}"
        )

    per_query = defaultdict(list)

    for line_no, row in enumerate(rows, start=2):
        qid = row["query_id"].strip()
        doc_id = row["source_doc_id"].strip()
        unit_id = row["source_unit_id"].strip()

        if qid not in query_map:
            raise ValueError(
                f"Unknown query_id={qid!r} at row {line_no}"
            )

        query = query_map[qid]

        if row["dataset_id"] != query["dataset_id"]:
            raise ValueError(
                f"{qid}: qrel dataset mismatch"
            )

        key = (doc_id, unit_id)

        if key not in document_units:
            raise ValueError(
                f"{qid}: qrel references unknown unit {key}"
            )

        if row["document_version"] != document_units[key]["document_version"]:
            raise ValueError(
                f"{qid}: document version mismatch for {unit_id}"
            )

        try:
            grade = int(row["relevance_grade"])
        except ValueError as exc:
            raise ValueError(
                f"{qid}: invalid relevance_grade"
            ) from exc

        if grade < 0:
            raise ValueError(
                f"{qid}: negative relevance grade"
            )

        conflict_flag = row[
            "conflicting_unit_flag"
        ].strip().lower()

        if conflict_flag not in {"true", "false"}:
            raise ValueError(
                f"{qid}: invalid conflicting_unit_flag"
            )

        per_query[qid].append(row)

    # Evaluate query-specific qrel contracts.
    for qid, query in query_map.items():
        relevant = [
            row
            for row in per_query.get(qid, [])
            if int(row["relevance_grade"]) > 0
        ]

        answerability = query["answerability"]

        if answerability == "unanswerable":
            if relevant:
                raise ValueError(
                    f"{qid}: unanswerable query has positive qrels"
                )

        elif answerability == "answerable":
            expected = 2 if query["requires_multi_hop"].lower() == "true" else 1

            if len(relevant) != expected:
                raise ValueError(
                    f"{qid}: expected {expected} positive qrels; "
                    f"found {len(relevant)}"
                )

            if any(
                row["conflicting_unit_flag"].strip().lower() == "true"
                for row in relevant
            ):
                raise ValueError(
                    f"{qid}: ordinary answerable query has conflicting qrel"
                )

        elif answerability == "conflict":
            if len(relevant) != 2:
                raise ValueError(
                    f"{qid}: conflict query must have exactly 2 positive qrels; "
                    f"found {len(relevant)}"
                )

            conflict_rows = [
                row
                for row in relevant
                if row["conflicting_unit_flag"].strip().lower() == "true"
            ]

            if len(conflict_rows) != 2:
                raise ValueError(
                    f"{qid}: both conflict qrels must be marked conflicting"
                )

            groups = {
                row["conflict_group_id"].strip()
                for row in conflict_rows
            }

            if groups != {query["conflict_group_id"].strip()}:
                raise ValueError(
                    f"{qid}: conflict group mismatch"
                )

    return rows, per_query


def validate_multi_hop(query_map, per_query):
    multi_hop = [
        row
        for row in query_map.values()
        if row["requires_multi_hop"].lower() == "true"
    ]

    if len(multi_hop) != 48:
        raise ValueError(
            f"Expected 48 multi-hop queries; found {len(multi_hop)}"
        )

    for query in multi_hop:
        qid = query["query_id"]

        positive = [
            row
            for row in per_query[qid]
            if int(row["relevance_grade"]) > 0
        ]

        if len(positive) < 2:
            raise ValueError(
                f"{qid}: multi-hop query lacks multiple positive evidence units"
            )

        source_units = {
            row["source_unit_id"]
            for row in positive
        }

        if len(source_units) < 2:
            raise ValueError(
                f"{qid}: multi-hop query must use distinct evidence units"
            )


def main() -> int:
    print("=== Tier A v0.3.1 Validator ===")
    print(f"Data: {DATA}")

    document_units, documents, document_rows = load_documents()

    print(
        f"DOCUMENTS: PASS ({len(documents)} documents / "
        f"{len(document_rows)} units)"
    )

    query_map, query_rows = load_queries()

    print(
        f"QUERIES: PASS ({len(query_rows)} canonical queries)"
    )

    qrel_rows, per_query = load_qrels(
        query_map,
        document_units,
    )

    print(
        f"QRELS: PASS ({len(qrel_rows)} judgments)"
    )

    validate_multi_hop(
        query_map,
        per_query,
    )

    print("MULTI-HOP CONTRACT: PASS (48 queries)")

    conflict_queries = [
        q
        for q in query_map.values()
        if q["answerability"] == "conflict"
    ]

    print(
        f"CONFLICT CONTRACT: PASS ({len(conflict_queries)} queries)"
    )

    unanswerable_queries = [
        q
        for q in query_map.values()
        if q["answerability"] == "unanswerable"
    ]

    print(
        f"UNANSWERABLE CONTRACT: PASS ({len(unanswerable_queries)} queries)"
    )

    print("\nTIER A VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"\nTIER A VALIDATION: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1)
