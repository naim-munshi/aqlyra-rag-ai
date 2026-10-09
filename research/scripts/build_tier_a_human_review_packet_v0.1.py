from __future__ import annotations

import csv
import hashlib
import random
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research/benchmark_v0.3/data/tier_a_v0.3.3"
OUT = ROOT / "research/benchmark_v0.3/review_v0.1"

QUERIES = DATA / "queries.csv"
DOCS = DATA / "documents.csv"

SEED = 20261007
TARGET_TOTAL = 120
PER_QUESTION_TYPE = 24

OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


queries = read_csv(QUERIES)
docs = read_csv(DOCS)

doc_to_source = {
    r["source_unit_id"]: r["source_doc_id"]
    for r in docs
}

question_types = sorted({r["question_type"] for r in queries})

if len(queries) != 240:
    raise SystemExit(f"Expected 240 queries, found {len(queries)}")

if len(question_types) != 5:
    raise SystemExit(
        f"Expected 5 question types, found {len(question_types)}: "
        f"{question_types}"
    )

rng = random.Random(SEED)

selected: list[dict[str, str]] = []

for qtype in question_types:
    candidates = [
        r.copy()
        for r in queries
        if r["question_type"] == qtype
    ]

    if len(candidates) != 48:
        raise SystemExit(
            f"{qtype}: expected 48 candidates, found {len(candidates)}"
        )

    # Deterministic but independent ordering per question type.
    rng_q = random.Random(SEED + sum(map(ord, qtype)))
    rng_q.shuffle(candidates)

    # First pass: try to maximize source-document coverage.
    by_doc: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        source_doc = doc_to_source.get(row["primary_source_doc_id"], "")
        by_doc.setdefault(source_doc, []).append(row)

    doc_keys = sorted(by_doc)
    rng_q.shuffle(doc_keys)

    chosen = []
    for source_doc in doc_keys:
        if by_doc[source_doc]:
            chosen.append(by_doc[source_doc][0])
        if len(chosen) >= PER_QUESTION_TYPE:
            break

    # Fallback to shuffled candidates if needed.
    if len(chosen) < PER_QUESTION_TYPE:
        chosen_ids = {r["query_id"] for r in chosen}
        for row in candidates:
            if row["query_id"] not in chosen_ids:
                chosen.append(row)
                if len(chosen) >= PER_QUESTION_TYPE:
                    break

    if len(chosen) != PER_QUESTION_TYPE:
        raise SystemExit(
            f"{qtype}: could not select {PER_QUESTION_TYPE} queries"
        )

    selected.extend(chosen)


if len(selected) != TARGET_TOTAL:
    raise SystemExit(
        f"Expected {TARGET_TOTAL} selected queries, got {len(selected)}"
    )


# Stable final order.
selected.sort(
    key=lambda r: (
        r["question_type"],
        r["query_id"],
    )
)


fields = [
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
    "distractor_unit_ids",
    "distractor_unit_count",
    "lexical_overlap_bucket",
    "requires_multi_hop",
    "review_status",
    "annotation_notes",
    "reviewer_decision",
    "gold_answer_ok",
    "gold_evidence_ok",
    "qrels_ok",
    "answerability_ok",
    "multi_hop_ok",
    "conflict_ok",
    "distractor_ok",
    "reviewer_notes",
]

packet = OUT / "tier_a_v0.3.3_human_review_packet_v0.1.csv"

with packet.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for row in selected:
        out = {k: row.get(k, "") for k in fields}

        # Reviewer fields intentionally remain blank.
        for k in fields:
            if k in {
                "reviewer_decision",
                "gold_answer_ok",
                "gold_evidence_ok",
                "qrels_ok",
                "answerability_ok",
                "multi_hop_ok",
                "conflict_ok",
                "distractor_ok",
                "reviewer_notes",
            }:
                out[k] = ""

        writer.writerow(out)


query_hash = sha256(QUERIES)
docs_hash = sha256(DOCS)
packet_hash = sha256(packet)

manifest = OUT / "tier_a_v0.3.3_human_review_manifest_v0.1.txt"

with manifest.open("w", encoding="utf-8") as f:
    f.write("Tier-A v0.3.3 Human Review Packet v0.1\n")
    f.write("========================================\n")
    f.write(f"selection_seed={SEED}\n")
    f.write(f"target_total={TARGET_TOTAL}\n")
    f.write(f"question_types={','.join(question_types)}\n")
    f.write(f"per_question_type={PER_QUESTION_TYPE}\n")
    f.write("selection_status=machine-generated; human review pending\n")
    f.write(f"queries_csv_sha256={query_hash}\n")
    f.write(f"documents_csv_sha256={docs_hash}\n")
    f.write(f"packet_csv_sha256={packet_hash}\n")


print("=== HUMAN REVIEW PACKET ===")
print("packet:", packet)
print("manifest:", manifest)
print("selected queries:", len(selected))
print("selection seed:", SEED)

print("\n=== QUESTION TYPE ===")
print(dict(Counter(r["question_type"] for r in selected)))

print("\n=== ANSWERABILITY ===")
print(dict(Counter(r["answerability"] for r in selected)))

print("\n=== SOURCE DOCUMENT COVERAGE ===")
source_docs = Counter(r["primary_source_doc_id"] for r in selected)
print("unique primary source docs:", len(source_docs))

print("\n=== MULTI-HOP ===")
print(dict(Counter(str(r["requires_multi_hop"]).lower() for r in selected)))

print("\n=== REVIEW STATUS ===")
print(dict(Counter(r["review_status"] for r in selected)))

print("\nHUMAN REVIEW PACKET BUILD: PASS")
