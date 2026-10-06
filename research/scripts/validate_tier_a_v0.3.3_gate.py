from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("research/benchmark_v0.3/data/tier_a_v0.3.3")
REPORT = Path("research/benchmark_v0.3/results/tier_a_v0.3.3_full_gate.txt")

FAIL = []
WARN = []

def read_csv(name):
    path = ROOT / name
    if not path.exists():
        FAIL.append(f"missing file: {name}")
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return reader.fieldnames or [], rows

doc_fields, docs = read_csv("documents.csv")
query_fields, queries = read_csv("queries.csv")
qrel_fields, qrels = read_csv("qrels.csv")

print("=== TIER A v0.3.3 FULL INTEGRITY GATE ===")
print(f"documents: {len(docs)}")
print(f"queries:   {len(queries)}")
print(f"qrels:     {len(qrels)}")

# ------------------------------------------------------------
# Structural counts
# ------------------------------------------------------------
if len(docs) != 288:
    FAIL.append(f"documents count = {len(docs)}, expected 288")

if len(queries) != 240:
    FAIL.append(f"queries count = {len(queries)}, expected 240")

expected_types = {
    "lexical-anchor": 48,
    "semantic-paraphrase": 48,
    "entity+attribute": 48,
    "multi-hop": 48,
    "distractor-heavy": 48,
}

expected_answerability = {
    "answerable": 192,
    "unanswerable": 24,
    "conflict": 24,
}

type_counts = Counter(q.get("question_type", "") for q in queries)
answerability_counts = Counter(q.get("answerability", "") for q in queries)

print("\n=== QUESTION TYPE COUNTS ===")
for k, v in sorted(type_counts.items()):
    print(f"{k}: {v}")

if type_counts != expected_types:
    FAIL.append(f"question-type distribution incorrect: {dict(type_counts)}")

print("\n=== ANSWERABILITY COUNTS ===")
for k, v in sorted(answerability_counts.items()):
    print(f"{k}: {v}")

if answerability_counts != expected_answerability:
    FAIL.append(
        f"answerability distribution incorrect: {dict(answerability_counts)}"
    )

# ------------------------------------------------------------
# ID uniqueness
# ------------------------------------------------------------
doc_keys = [(d.get("source_doc_id", ""), d.get("source_unit_id", "")) for d in docs]
query_ids = [q.get("query_id", "") for q in queries]

if len(doc_keys) != len(set(doc_keys)):
    FAIL.append("duplicate (source_doc_id, source_unit_id) pairs found")

if len(query_ids) != len(set(query_ids)):
    FAIL.append("duplicate query_id values found")

if any(not x[0] or not x[1] for x in doc_keys):
    FAIL.append("blank document/unit IDs found")

if any(not x for x in query_ids):
    FAIL.append("blank query IDs found")

# ------------------------------------------------------------
# Document map
# ------------------------------------------------------------
doc_map = {
    (d["source_doc_id"], d["source_unit_id"]): d.get("text", "")
    for d in docs
}

# ------------------------------------------------------------
# QREL structure
# ------------------------------------------------------------
qrels_by_query = defaultdict(list)

for r in qrels:
    qid = r.get("query_id", "")
    try:
        grade = int(r.get("relevance_grade", "0"))
    except ValueError:
        FAIL.append(f"non-integer relevance_grade in qrel for {qid}")
        continue

    if qid not in query_ids:
        FAIL.append(f"qrel references unknown query_id: {qid}")

    key = (r.get("source_doc_id", ""), r.get("source_unit_id", ""))

    if key not in doc_map:
        FAIL.append(f"qrel references unknown retrieval unit: {key}")

    if grade > 0:
        qrels_by_query[qid].append(r)

# ------------------------------------------------------------
# QREL evidence span exactness
# ------------------------------------------------------------
evidence_errors = []

for qid, rows in qrels_by_query.items():
    for r in rows:
        key = (r["source_doc_id"], r["source_unit_id"])
        text = doc_map.get(key, "")
        span = r.get("gold_evidence_span", "").strip()

        if not span:
            evidence_errors.append((qid, key, "empty evidence span"))
            continue

        if span not in text:
            evidence_errors.append(
                (qid, key, f"span not found: {span!r}")
            )

if evidence_errors:
    FAIL.append(
        f"gold evidence span mismatch count = {len(evidence_errors)}"
    )

print("\n=== GOLD EVIDENCE SPAN CHECK ===")
print(f"errors: {len(evidence_errors)}")

# ------------------------------------------------------------
# Gold answer consistency
# ------------------------------------------------------------
def normalize(text: str) -> str:
    text = text.lower().strip()

    text = re.sub(
        r"(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})",
        r"\1-\2",
        text,
    )

    text = re.sub(
        r"\bfrom\s+(\d{1,2}:\d{2})\s+to\s+(\d{1,2}:\d{2})\b",
        r"\1-\2",
        text,
    )

    text = re.sub(
        r"\b(\d{1,2}:\d{2})\s+to\s+(\d{1,2}:\d{2})\b",
        r"\1-\2",
        text,
    )

    text = re.sub(r"\s+", " ", text)
    return text

gold_errors = []

for q in queries:
    if q.get("answerability") != "answerable":
        continue

    if q.get("requires_multi_hop", "").lower() == "true":
        continue

    qid = q["query_id"]
    answer = q.get("gold_answer", "").strip()

    evidence = " ".join(
        r.get("gold_evidence_span", "")
        for r in qrels_by_query.get(qid, [])
    )

    if answer and normalize(answer) not in normalize(evidence):
        gold_errors.append((qid, answer, evidence))

if gold_errors:
    FAIL.append(
        f"direct gold/evidence mismatch count = {len(gold_errors)}"
    )

print("\n=== DIRECT GOLD/EVIDENCE CHECK ===")
print(f"errors: {len(gold_errors)}")

# ------------------------------------------------------------
# Unanswerable invariant
# ------------------------------------------------------------
unanswerable_errors = []

for q in queries:
    if q.get("answerability") == "unanswerable":
        positives = qrels_by_query.get(q["query_id"], [])
        if positives:
            unanswerable_errors.append(
                (q["query_id"], len(positives))
            )

if unanswerable_errors:
    FAIL.append(
        f"unanswerable queries with positive qrels = "
        f"{len(unanswerable_errors)}"
    )

print("\n=== UNANSWERABLE CHECK ===")
print(f"positive-qrel violations: {len(unanswerable_errors)}")

# ------------------------------------------------------------
# Multi-hop invariant
# ------------------------------------------------------------
multi_hop_errors = []

for q in queries:
    if q.get("requires_multi_hop", "").lower() == "true":
        positives = qrels_by_query.get(q["query_id"], [])

        if len(positives) < 2:
            multi_hop_errors.append(
                (q["query_id"], len(positives))
            )

if multi_hop_errors:
    FAIL.append(
        f"multi-hop queries with <2 positive units = "
        f"{len(multi_hop_errors)}"
    )

print("\n=== MULTI-HOP CHECK ===")
print(f"errors: {len(multi_hop_errors)}")

# ------------------------------------------------------------
# Conflict invariant
# ------------------------------------------------------------
conflict_queries = [
    q for q in queries if q.get("answerability") == "conflict"
]

conflict_errors = []

conflict_group_fields = [
    "conflict_group_id",
    "conflict_id",
    "conflict_group",
]

conflict_field = next(
    (f for f in conflict_group_fields if f in query_fields),
    None,
)

if not conflict_field:
    WARN.append(
        "No explicit conflict-group field found in queries.csv; "
        "conflict-group consistency could not be fully verified."
    )

for q in conflict_queries:
    positives = qrels_by_query.get(q["query_id"], [])

    if len(positives) < 2:
        conflict_errors.append(
            (q["query_id"], "fewer than 2 positive qrels")
        )
        continue

    if conflict_field:
        group = q.get(conflict_field, "").strip()

        if not group:
            conflict_errors.append(
                (q["query_id"], f"blank {conflict_field}")
            )

if conflict_errors:
    FAIL.append(
        f"conflict structure errors = {len(conflict_errors)}"
    )

print("\n=== CONFLICT CHECK ===")
print(f"conflict queries: {len(conflict_queries)}")
print(f"errors: {len(conflict_errors)}")
if conflict_field:
    print(f"group field: {conflict_field}")

# ------------------------------------------------------------
# Duplicate-word / grammar regression
# ------------------------------------------------------------
dup_errors = []
grammar_errors = []

countable = (
    "requests|appointments|transactions|passenger trips|"
    "applications|patients|parcels|tickets|bookings|visits|"
    "enrollments|cases|inspections|registrations"
)

for q in queries:
    text = q.get("question", "")

    if re.search(r"\b([A-Za-z]+)\s+\1\b", text, re.I):
        dup_errors.append((q["query_id"], text))

    if re.search(
        rf"\bHow much\s+({countable})\b",
        text,
        re.I,
    ):
        grammar_errors.append((q["query_id"], text))

if dup_errors:
    FAIL.append(f"duplicate-word errors = {len(dup_errors)}")

if grammar_errors:
    FAIL.append(f"countable-noun grammar errors = {len(grammar_errors)}")

print("\n=== LANGUAGE REGRESSION CHECK ===")
print(f"duplicate-word errors: {len(dup_errors)}")
print(f"countable-noun grammar errors: {len(grammar_errors)}")

# ------------------------------------------------------------
# Query template diversity
# ------------------------------------------------------------
def normalize_template(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\bcedar\b|\bmaple\b|\bharbor\b|\bnorthstar\b|\bjuniper\b|\briverside\b", "<ENTITY>", text)
    text = re.sub(r"\b\d+\b", "<NUM>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

templates = Counter(
    normalize_template(q["question"])
    for q in queries
)

repeated_templates = [
    (template, count)
    for template, count in templates.items()
    if count >= 4
]

print("\n=== TEMPLATE DIVERSITY ===")
print(f"unique normalized templates: {len(templates)}")
print(f"templates repeated >=4x: {len(repeated_templates)}")

for template, count in sorted(
    repeated_templates,
    key=lambda x: (-x[1], x[0])
)[:20]:
    print(f"{count:>3}x  {template}")

# Do not automatically fail solely because templates repeat.
# This is a human-review diagnostic.

# ------------------------------------------------------------
# Question leakage / exact duplicate questions
# ------------------------------------------------------------
question_texts = Counter(
    q.get("question", "").strip().lower()
    for q in queries
)

exact_duplicates = [
    (text, count)
    for text, count in question_texts.items()
    if count > 1
]

if exact_duplicates:
    FAIL.append(
        f"exact duplicate question texts = {len(exact_duplicates)}"
    )

print("\n=== QUESTION DUPLICATION ===")
print(f"exact duplicate question texts: {len(exact_duplicates)}")

# ------------------------------------------------------------
# Change-provenance check vs v0.3.2
# ------------------------------------------------------------
OLD = ROOT.parent / "tier_a_v0.3.2"
provenance_errors = []

if OLD.exists():
    with (OLD / "queries.csv").open(newline="", encoding="utf-8") as f:
        old_rows = {r["query_id"]: r for r in csv.DictReader(f)}

    with (ROOT / "queries.csv").open(newline="", encoding="utf-8") as f:
        new_rows = {r["query_id"]: r for r in csv.DictReader(f)}

    if set(old_rows) != set(new_rows):
        provenance_errors.append("query ID set changed")

    for qid in old_rows:
        for field in query_fields:
            if field == "question":
                continue

            if old_rows[qid].get(field) != new_rows[qid].get(field):
                provenance_errors.append(
                    f"{qid}: non-question field changed: {field}"
                )

    for filename in ["documents.csv", "qrels.csv"]:
        old_hash = hashlib.sha256((OLD / filename).read_bytes()).hexdigest()
        new_hash = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()

        if old_hash != new_hash:
            provenance_errors.append(
                f"{filename} changed relative to v0.3.2"
            )

else:
    WARN.append("v0.3.2 source directory not found; lineage check skipped.")

if provenance_errors:
    FAIL.append(
        f"provenance errors = {len(provenance_errors)}"
    )

print("\n=== PROVENANCE CHECK ===")
print(f"errors: {len(provenance_errors)}")

# ------------------------------------------------------------
# Final status + report
# ------------------------------------------------------------
status = "PASS" if not FAIL else "FAIL"

print("\n=== FINAL STATUS ===")
print(f"STATUS: {status}")

if FAIL:
    print("\nFAILURES:")
    for item in FAIL:
        print(f"- {item}")

if WARN:
    print("\nWARNINGS:")
    for item in WARN:
        print(f"- {item}")

REPORT.parent.mkdir(parents=True, exist_ok=True)

lines = [
    "Aqlyra Tier A v0.3.3 Full Integrity Gate",
    "=" * 44,
    f"STATUS: {status}",
    "",
    f"documents={len(docs)}",
    f"queries={len(queries)}",
    f"qrels={len(qrels)}",
    f"evidence_span_errors={len(evidence_errors)}",
    f"gold_evidence_errors={len(gold_errors)}",
    f"unanswerable_errors={len(unanswerable_errors)}",
    f"multi_hop_errors={len(multi_hop_errors)}",
    f"conflict_errors={len(conflict_errors)}",
    f"duplicate_word_errors={len(dup_errors)}",
    f"grammar_errors={len(grammar_errors)}",
    f"exact_duplicate_questions={len(exact_duplicates)}",
    f"provenance_errors={len(provenance_errors)}",
    "",
    "FAILURES:",
    *[f"- {x}" for x in FAIL],
    "",
    "WARNINGS:",
    *[f"- {x}" for x in WARN],
]

REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nREPORT: {REPORT}")

if status != "PASS":
    raise SystemExit(1)
