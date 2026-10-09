from __future__ import annotations

import ast
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research/benchmark_v0.3/data/tier_a_v0.3.3"

DOCS = DATA / "documents.csv"
QUERIES = DATA / "queries.csv"
QRELS = DATA / "qrels.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def parse_id_list(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []

    # JSON list first.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass

    # Python-style list fallback.
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass

    # Conservative delimiter fallback.
    if ";" in raw:
        return [x.strip() for x in raw.split(";") if x.strip()]
    if "," in raw:
        return [x.strip() for x in raw.split(",") if x.strip()]

    return [raw]


docs = read_csv(DOCS)
queries = read_csv(QUERIES)
qrels = read_csv(QRELS)

print("=== TIER-A ANNOTATION QUALITY AUDIT v0.1 ===")
print("documents:", len(docs))
print("queries:", len(queries))
print("qrels:", len(qrels))

doc_by_unit = {r["source_unit_id"]: r for r in docs}
query_by_id = {r["query_id"]: r for r in queries}

qrels_by_query: dict[str, list[dict[str, str]]] = defaultdict(list)
for row in qrels:
    qrels_by_query[row["query_id"]].append(row)

errors: list[str] = []
warnings: list[str] = []


# ---------------------------------------------------------------------------
# 1. Basic cardinality
# ---------------------------------------------------------------------------
print("\n=== CARDINALITY ===")

checks = {
    "documents_288": len(docs) == 288,
    "queries_240": len(queries) == 240,
    "qrels_288": len(qrels) == 288,
}

for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        errors.append(name)


# ---------------------------------------------------------------------------
# 2. Query status distribution
# ---------------------------------------------------------------------------
print("\n=== QUERY DISTRIBUTION ===")

answerability = Counter(r["answerability"] for r in queries)
question_type = Counter(r["question_type"] for r in queries)
review_status = Counter(r["review_status"] for r in queries)
multi_hop = Counter(str(r["requires_multi_hop"]).lower() for r in queries)
overlap = Counter(r["lexical_overlap_bucket"] for r in queries)

print("answerability:", dict(answerability))
print("question_type:", dict(question_type))
print("review_status:", dict(review_status))
print("requires_multi_hop:", dict(multi_hop))
print("lexical_overlap_bucket:", dict(overlap))


# ---------------------------------------------------------------------------
# 3. Query -> qrels metadata consistency
# ---------------------------------------------------------------------------
print("\n=== QUERY / QREL CONSISTENCY ===")

for q in queries:
    qid = q["query_id"]
    category = q["answerability"]
    rel_rows = qrels_by_query.get(qid, [])

    try:
        declared_gold_count = int(q["gold_evidence_count"])
    except ValueError:
        errors.append(f"{qid}: invalid gold_evidence_count")
        continue

    actual_qrel_count = len(rel_rows)

    # For this benchmark:
    # answerable/conflict queries must have qrels;
    # unanswerable queries must not.
    expected_nonzero = category in {"answerable", "conflict"}

    if expected_nonzero and actual_qrel_count == 0:
        errors.append(f"{qid}: {category} query has zero qrels")

    if category == "unanswerable" and actual_qrel_count != 0:
        errors.append(
            f"{qid}: unanswerable query has {actual_qrel_count} qrels"
        )

    # gold_evidence_count should match the number of qrel rows for
    # benchmark annotations.
    if declared_gold_count != actual_qrel_count:
        errors.append(
            f"{qid}: gold_evidence_count={declared_gold_count}, "
            f"qrel_count={actual_qrel_count}"
        )

    requires_multi = parse_bool(q["requires_multi_hop"])
    if requires_multi and actual_qrel_count < 2:
        errors.append(
            f"{qid}: requires_multi_hop=true but has only "
            f"{actual_qrel_count} qrels"
        )

    if category in {"answerable", "conflict"} and not q["gold_answer"].strip():
        warnings.append(f"{qid}: answerable/conflict query has empty gold_answer")


# ---------------------------------------------------------------------------
# 4. QREL document metadata consistency
# ---------------------------------------------------------------------------
print("\n=== QREL / DOCUMENT METADATA ===")

for r in qrels:
    qid = r["query_id"]
    uid = r["source_unit_id"]

    doc = doc_by_unit.get(uid)
    if doc is None:
        errors.append(f"{qid}: qrel references unknown unit {uid}")
        continue

    if r["source_doc_id"] != doc["source_doc_id"]:
        errors.append(
            f"{qid}/{uid}: source_doc_id mismatch "
            f"qrel={r['source_doc_id']} doc={doc['source_doc_id']}"
        )

    if r["document_version"] != doc["document_version"]:
        errors.append(
            f"{qid}/{uid}: document_version mismatch "
            f"qrel={r['document_version']} doc={doc['document_version']}"
        )

    if r["dataset_id"] != doc["dataset_id"]:
        errors.append(
            f"{qid}/{uid}: dataset_id mismatch "
            f"qrel={r['dataset_id']} doc={doc['dataset_id']}"
        )

    if not r["gold_evidence_span"].strip():
        warnings.append(f"{qid}/{uid}: empty gold_evidence_span")


# ---------------------------------------------------------------------------
# 5. Distractor integrity
# ---------------------------------------------------------------------------
print("\n=== DISTRACTOR INTEGRITY ===")

distractor_errors = 0

for q in queries:
    qid = q["query_id"]
    distractors = parse_id_list(q["distractor_unit_ids"])

    try:
        declared_count = int(q["distractor_unit_count"])
    except ValueError:
        errors.append(f"{qid}: invalid distractor_unit_count")
        continue

    if declared_count != len(distractors):
        errors.append(
            f"{qid}: distractor_unit_count={declared_count}, "
            f"parsed={len(distractors)}"
        )
        distractor_errors += 1

    unknown = [uid for uid in distractors if uid not in doc_by_unit]
    if unknown:
        errors.append(
            f"{qid}: unknown distractor units {unknown[:5]}"
        )
        distractor_errors += 1

    qrel_units = {
        r["source_unit_id"] for r in qrels_by_query.get(qid, [])
    }

    overlap_units = sorted(set(distractors) & qrel_units)
    if overlap_units:
        errors.append(
            f"{qid}: distractor overlaps gold/qrel units {overlap_units}"
        )
        distractor_errors += 1

print("distractor-related hard errors:", distractor_errors)


# ---------------------------------------------------------------------------
# 6. Conflict integrity
# ---------------------------------------------------------------------------
print("\n=== CONFLICT INTEGRITY ===")

conflict_queries = [
    q for q in queries if q["answerability"] == "conflict"
]

conflict_errors = 0

for q in conflict_queries:
    qid = q["query_id"]
    group = q["conflict_group_id"].strip()

    if not group:
        errors.append(f"{qid}: conflict query has empty conflict_group_id")
        conflict_errors += 1

    rel_rows = qrels_by_query.get(qid, [])
    if len(rel_rows) < 2:
        errors.append(
            f"{qid}: conflict query has fewer than 2 qrel rows"
        )
        conflict_errors += 1

    for r in rel_rows:
        if str(r["conflicting_unit_flag"]).strip().lower() != "true":
            errors.append(
                f"{qid}/{r['source_unit_id']}: "
                f"conflicting_unit_flag is not true"
            )
            conflict_errors += 1

        if r["conflict_group_id"].strip() != group:
            errors.append(
                f"{qid}/{r['source_unit_id']}: conflict_group_id mismatch"
            )
            conflict_errors += 1

print("conflict-related hard errors:", conflict_errors)


# ---------------------------------------------------------------------------
# 7. Duplicate / uniqueness checks
# ---------------------------------------------------------------------------
print("\n=== UNIQUENESS ===")

doc_ids = [r["source_unit_id"] for r in docs]
query_ids = [r["query_id"] for r in queries]

duplicate_doc_ids = [
    x for x, c in Counter(doc_ids).items() if c > 1
]
duplicate_query_ids = [
    x for x, c in Counter(query_ids).items() if c > 1
]
duplicate_pairs = [
    x
    for x, c in Counter(
        (r["query_id"], r["source_unit_id"]) for r in qrels
    ).items()
    if c > 1
]

print("duplicate document IDs:", len(duplicate_doc_ids))
print("duplicate query IDs:", len(duplicate_query_ids))
print("duplicate qrel pairs:", len(duplicate_pairs))

if duplicate_doc_ids:
    errors.append("duplicate document IDs")
if duplicate_query_ids:
    errors.append("duplicate query IDs")
if duplicate_pairs:
    errors.append("duplicate qrel pairs")


# ---------------------------------------------------------------------------
# 8. Review readiness
# ---------------------------------------------------------------------------
print("\n=== REVIEW READINESS ===")

draft_count = sum(
    1 for q in queries
    if q["review_status"].strip().lower() != "reviewed"
)

print("queries not marked reviewed:", draft_count)

if draft_count > 0:
    warnings.append(
        f"{draft_count} queries remain not marked reviewed; "
        "benchmark should not be described as human-frozen."
    )


# ---------------------------------------------------------------------------
# Final gate
# ---------------------------------------------------------------------------
print("\n=== FINAL GATE ===")

if errors:
    print("hard errors:", len(errors))
    for item in errors[:50]:
        print("FAIL:", item)
else:
    print("hard errors: 0")

print("warnings:", len(warnings))
for item in warnings[:25]:
    print("WARN:", item)

if errors:
    raise SystemExit("\nTIER-A ANNOTATION QUALITY AUDIT: FAIL")

print("\nTIER-A ANNOTATION QUALITY AUDIT: PASS")
