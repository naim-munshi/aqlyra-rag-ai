#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research" / "benchmark_v0.3" / "data" / "tier_a_v0.3.1"

BANNED_LEAK_PATTERNS = [
    r"TIERA_",
    r"_U\d+",
    r"\bcoverage\b",
    r"\bmask(?:ing|ed)?\b",
    r"\bRRF\b",
    r"LEXICAL_ONLY",
    r"DENSE_ONLY",
    r"AQ-LYRA",
    r"UNION_RRF",
]

def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fail(message: str):
    raise SystemExit(f"AUDIT FAIL: {message}")


documents = read_csv(DATA / "documents.csv")
queries = read_csv(DATA / "queries.csv")
qrels = read_csv(DATA / "qrels.csv")

print("=== Tier A Content Quality Audit v0.3.1 ===")
print(f"documents      = {len(documents)}")
print(f"queries        = {len(queries)}")
print(f"qrels          = {len(qrels)}")


# ---------------------------------------------------------
# Document integrity
# ---------------------------------------------------------
doc_map = {}
doc_groups = defaultdict(list)
text_hashes = Counter()

for row in documents:
    key = (row["source_doc_id"], row["source_unit_id"])

    if key in doc_map:
        fail(f"duplicate document unit: {key}")

    text = row["text"].strip()

    if not text:
        fail(f"empty text: {key}")

    observed_hash = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    if observed_hash != row["content_hash_sha256"]:
        fail(f"hash mismatch: {key}")

    doc_map[key] = row
    doc_groups[row["source_doc_id"]].append(row)
    text_hashes[observed_hash] += 1


print("\nDOCUMENT INTEGRITY")
print(
    f"unique_documents = {len(doc_groups)}"
)
print(
    f"unique_units     = {len(doc_map)}"
)
print(
    f"duplicate_text_hashes = "
    f"{sum(v - 1 for v in text_hashes.values() if v > 1)}"
)

if len(doc_groups) != 48:
    fail("expected exactly 48 documents")

if len(doc_map) != 288:
    fail("expected exactly 288 retrieval units")


# ---------------------------------------------------------
# Domain balance
# ---------------------------------------------------------
strata = Counter()

for row in documents:
    # source_doc_id -> deterministic numbering -> stratum
    doc_number = int(
        row["source_doc_id"].split("_")[1]
    )
    stratum = f"STR{((doc_number - 1) // 6) + 1:02d}"
    strata[stratum] += 1


print("\nDOCUMENT STRATA")
for key in sorted(strata):
    print(f"{key}: units={strata[key]}")

if set(strata.values()) != {36}:
    fail("each stratum should contain exactly 36 retrieval units")


# ---------------------------------------------------------
# Query integrity
# ---------------------------------------------------------
query_ids = set()
query_by_doc = defaultdict(list)
answerability = Counter()
question_types = Counter()

for row in queries:
    qid = row["query_id"]

    if qid in query_ids:
        fail(f"duplicate query_id: {qid}")

    query_ids.add(qid)
    query_by_doc[row["primary_source_doc_id"]].append(row)

    answerability[row["answerability"]] += 1
    question_types[row["question_type"]] += 1

    question = row["question"].strip()

    if not question:
        fail(f"empty question: {qid}")

    for pattern in BANNED_LEAK_PATTERNS:
        if re.search(pattern, question, flags=re.IGNORECASE):
            fail(
                f"potential query leakage: {qid}, pattern={pattern!r}"
            )

    if len(question.split()) < 5:
        print(
            f"WARNING: very short question: {qid}: {question}"
        )

    if len(question.split()) > 45:
        print(
            f"WARNING: very long question: {qid}"
        )


print("\nQUERY DISTRIBUTION")
print("answerability:")
for key, value in sorted(answerability.items()):
    print(f"  {key}: {value}")

print("question_types:")
for key, value in sorted(question_types.items()):
    print(f"  {key}: {value}")


# ---------------------------------------------------------
# Per-document query allocation
# ---------------------------------------------------------
print("\nPER-DOCUMENT QUERY ALLOCATION")

for doc_id in sorted(query_by_doc):
    rows = query_by_doc[doc_id]

    if len(rows) != 5:
        fail(
            f"{doc_id}: expected 5 queries, found {len(rows)}"
        )

    types = Counter(
        row["question_type"]
        for row in rows
    )

    if set(types) != {
        "lexical-anchor",
        "semantic-paraphrase",
        "entity+attribute",
        "multi-hop",
        "distractor-heavy",
    }:
        fail(
            f"{doc_id}: invalid question type set: {set(types)}"
        )


# ---------------------------------------------------------
# QREL integrity
# ---------------------------------------------------------
qrels_by_query = defaultdict(list)

for row in qrels:
    qid = row["query_id"]

    if qid not in query_ids:
        fail(f"qrel references unknown query: {qid}")

    key = (
        row["source_doc_id"],
        row["source_unit_id"],
    )

    if key not in doc_map:
        fail(
            f"{qid}: qrel references unknown unit: {key}"
        )

    if (
        row["gold_evidence_span"]
        != doc_map[key]["text"]
    ):
        fail(
            f"{qid}: gold_evidence_span does not exactly match "
            f"document text for {key}"
        )

    qrels_by_query[qid].append(row)


print("\nQREL INTEGRITY")
print(f"qrel_rows = {len(qrels)}")

for qid, query in (
    {
        row["query_id"]: row
        for row in queries
    }
).items():

    relevant = [
        r for r in qrels_by_query[qid]
        if int(r["relevance_grade"]) > 0
    ]

    answerability_value = query["answerability"]
    multi_hop = (
        query["requires_multi_hop"].lower() == "true"
    )

    if answerability_value == "unanswerable":
        if relevant:
            fail(
                f"{qid}: unanswerable query has positive evidence"
            )

    elif answerability_value == "answerable":
        expected = 2 if multi_hop else 1

        if len(relevant) != expected:
            fail(
                f"{qid}: expected {expected} positive qrels, "
                f"found {len(relevant)}"
            )

    elif answerability_value == "conflict":
        if len(relevant) != 2:
            fail(
                f"{qid}: conflict query should have exactly 2 "
                f"positive qrels"
            )

        if not all(
            r["conflicting_unit_flag"].lower() == "true"
            for r in relevant
        ):
            fail(
                f"{qid}: conflict qrels not consistently marked"
            )


# ---------------------------------------------------------
# Multi-hop analysis
# ---------------------------------------------------------
multi_hop_queries = [
    q for q in queries
    if q["requires_multi_hop"].lower() == "true"
]

print("\nMULTI-HOP REVIEW")
print(f"multi_hop_queries = {len(multi_hop_queries)}")

for q in multi_hop_queries:
    qid = q["query_id"]

    relevant = [
        r for r in qrels_by_query[qid]
        if int(r["relevance_grade"]) > 0
    ]

    units = {
        r["source_unit_id"]
        for r in relevant
    }

    if len(units) < 2:
        fail(
            f"{qid}: multi-hop query does not use two distinct units"
        )


# ---------------------------------------------------------
# Conflict review
# ---------------------------------------------------------
conflict_queries = [
    q for q in queries
    if q["answerability"] == "conflict"
]

print("\nCONFLICT REVIEW")
print(f"conflict_queries = {len(conflict_queries)}")

for q in conflict_queries:
    qid = q["query_id"]

    rows = [
        r for r in qrels_by_query[qid]
        if int(r["relevance_grade"]) > 0
    ]

    groups = {
        r["conflict_group_id"]
        for r in rows
    }

    if len(groups) != 1:
        fail(
            f"{qid}: inconsistent conflict group"
        )

    texts = [
        doc_map[
            (r["source_doc_id"], r["source_unit_id"])
        ]["text"]
        for r in rows
    ]

    if len(set(texts)) != 2:
        fail(
            f"{qid}: conflict evidence units are identical"
        )


# ---------------------------------------------------------
# Template repetition analysis
# ---------------------------------------------------------
print("\nTEMPLATE REPETITION REVIEW")

question_stems = Counter()

for row in queries:
    q = row["question"].strip()

    normalized = re.sub(
        r"\b(?:What|When|Which|How|During|Does)\b",
        "<QWORD>",
        q,
        flags=re.IGNORECASE,
    )

    normalized = re.sub(
        r"\b[A-Z][A-Za-z-]+\b",
        "<ENTITY>",
        normalized,
    )

    question_stems[normalized] += 1

for stem, count in question_stems.most_common(10):
    if count >= 12:
        print(
            f"WARNING: repeated template pattern ({count}x): {stem}"
        )


# ---------------------------------------------------------
# Content sample
# ---------------------------------------------------------
print("\n=== STRATIFIED CONTENT SAMPLE ===")

seen_strata = set()

for row in documents:
    doc_id = row["source_doc_id"]
    doc_number = int(doc_id.split("_")[1])
    stratum = f"STR{((doc_number - 1) // 6) + 1:02d}"

    if stratum in seen_strata:
        continue

    seen_strata.add(stratum)

    print(f"\n[{stratum}] {doc_id}")

    for unit in doc_groups[doc_id]:
        print(
            f"  {unit['source_unit_id']} "
            f"[{unit['unit_order']}] "
            f"{unit['text']}"
        )

    selected = query_by_doc[doc_id]

    for q in selected:
        print(
            f"  QUERY {q['query_id']} "
            f"[{q['question_type']}/{q['answerability']}] "
            f"{q['question']}"
        )

        if q["gold_answer"]:
            print(
                f"    GOLD: {q['gold_answer']}"
            )


print("\n=== AUDIT RESULT ===")
print(
    "Structural/content-reference checks: PASS"
)
print(
    "Human semantic review is still REQUIRED before freeze."
)
