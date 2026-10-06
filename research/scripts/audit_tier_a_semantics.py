#!/usr/bin/env python3

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research" / "benchmark_v0.3" / "data" / "tier_a_v0.3.2"
REPORT = ROOT / "research" / "benchmark_v0.3" / "results" / "tier_a_semantic_audit_v0.3.2.txt"

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "what", "when", "which", "how", "does", "can",
    "do", "under", "during", "for", "at", "of",
    "to", "in", "on", "with", "from", "and",
    "or", "be", "by", "this", "that", "as",
    "normal", "standard", "listed", "published",
    "recorded", "routine", "daily", "window",
}

NAME_PREFIXES = {
    "Cedar", "Maple", "Harbor",
    "Northstar", "Juniper", "Riverside",
}

def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tokens(text: str) -> set[str]:
    value = text.lower()

    value = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        "<num>",
        value,
    )

    value = re.sub(
        r"\b\d{1,2}:\d{2}-\d{1,2}:\d{2}\b",
        "<time>",
        value,
    )

    words = re.findall(r"[a-z]+(?:-[a-z]+)?|<num>|<time>", value)

    return {
        word
        for word in words
        if word not in STOPWORDS
    }


def normalized_question(text: str) -> str:
    value = text.lower()

    value = re.sub(
        r"\b(?:cedar|maple|harbor|northstar|juniper|riverside)\b",
        "<entity>",
        value,
    )

    value = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        "<value>",
        value,
    )

    value = re.sub(
        r"\b\d{1,2}:\d{2}-\d{1,2}:\d{2}\b",
        "<time>",
        value,
    )

    value = re.sub(r"\s+", " ", value).strip()

    return value


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0

    union = a | b

    if not union:
        return 0.0

    return len(a & b) / len(union)


documents = read_csv(DATA / "documents.csv")
queries = read_csv(DATA / "queries.csv")
qrels = read_csv(DATA / "qrels.csv")

doc_map = {
    (r["source_doc_id"], r["source_unit_id"]): r["text"]
    for r in documents
}

qmap = {
    r["query_id"]: r
    for r in queries
}

qrels_by_query = defaultdict(list)

for row in qrels:
    qrels_by_query[row["query_id"]].append(row)

hard_errors = []
warnings = []

# ---------------------------------------------------------
# Basic counts
# ---------------------------------------------------------
if len(documents) != 288:
    hard_errors.append(
        f"Expected 288 retrieval units; found {len(documents)}"
    )

if len(queries) != 240:
    hard_errors.append(
        f"Expected 240 queries; found {len(queries)}"
    )

if len(qrels) != 288:
    hard_errors.append(
        f"Expected 288 qrels; found {len(qrels)}"
    )

# ---------------------------------------------------------
# Query template repetition
# ---------------------------------------------------------
template_counts = Counter(
    normalized_question(q["question"])
    for q in queries
)

repeated_templates = [
    (template, count)
    for template, count in template_counts.items()
    if count >= 12
]

if repeated_templates:
    warnings.append(
        "HIGH TEMPLATE REPETITION: "
        + "; ".join(
            f"{count}x [{template}]"
            for template, count in sorted(
                repeated_templates,
                key=lambda x: -x[1],
            )[:10]
        )
    )

# ---------------------------------------------------------
# Near-duplicate questions
# ---------------------------------------------------------
question_sets = {
    q["query_id"]: tokens(q["question"])
    for q in queries
}

near_duplicates = []

for (qid_a, set_a), (qid_b, set_b) in combinations(
    question_sets.items(),
    2,
):
    score = jaccard(set_a, set_b)

    if score >= 0.85:
        if (
            qmap[qid_a]["primary_source_doc_id"]
            != qmap[qid_b]["primary_source_doc_id"]
        ):
            near_duplicates.append(
                (score, qid_a, qid_b)
            )

near_duplicates.sort(reverse=True)

if near_duplicates:
    warnings.append(
        f"NEAR-DUPLICATE QUESTIONS: "
        f"{len(near_duplicates)} cross-document pairs >= 0.85 similarity"
    )

# ---------------------------------------------------------
# Qrel vs distractor integrity
# ---------------------------------------------------------
distractor_errors = 0
gold_answer_leaks = 0

for q in queries:
    qid = q["query_id"]

    distractors = {
        value.strip()
        for value in q["distractor_unit_ids"].split(";")
        if value.strip()
    }

    positive_units = {
        r["source_unit_id"]
        for r in qrels_by_query[qid]
        if int(r["relevance_grade"]) > 0
    }

    if positive_units & distractors:
        distractor_errors += 1
        hard_errors.append(
            f"{qid}: distractor unit overlaps positive gold evidence"
        )

    answerability = q["answerability"]
    answer = q["gold_answer"].strip()

    if answerability == "answerable" and answer:
        direct = [
            r
            for r in qrels_by_query[qid]
            if int(r["relevance_grade"]) > 0
        ]

        if q["requires_multi_hop"].lower() != "true":
            evidence_text = " ".join(
                r["gold_evidence_span"]
                for r in direct
            )

            if answer not in evidence_text:
                gold_answer_leaks += 1

if gold_answer_leaks:
    warnings.append(
        f"DIRECT GOLD ANSWER NOT LITERALLY PRESENT IN "
        f"EVIDENCE: {gold_answer_leaks} queries"
    )

# ---------------------------------------------------------
# Unanswerable checks
# ---------------------------------------------------------
unanswerable_signal_errors = []

for q in queries:
    if q["answerability"] != "unanswerable":
        continue

    text = " ".join(
        doc_map[
            (
                r["source_doc_id"],
                r["source_unit_id"],
            )
        ]
        for r in documents
        if r["source_doc_id"]
        == q["primary_source_doc_id"]
    ).lower()

    question = q["question"].lower()

    signals = []

    if "email" in question:
        signals = ["email", "e-mail"]
    elif "cancel" in question:
        signals = ["cancel", "cancellation"]
    else:
        continue

    if any(signal in text for signal in signals):
        unanswerable_signal_errors.append(
            q["query_id"]
        )

if unanswerable_signal_errors:
    warnings.append(
        "UNANSWERABLE TARGET MAY EXIST IN SOURCE TEXT: "
        + ", ".join(unanswerable_signal_errors)
    )

# ---------------------------------------------------------
# Multi-hop arithmetic validity
# ---------------------------------------------------------
multihop_errors = []

for q in queries:
    if q["requires_multi_hop"].lower() != "true":
        continue

    positive = [
        r
        for r in qrels_by_query[q["query_id"]]
        if int(r["relevance_grade"]) > 0
    ]

    if len(positive) != 2:
        multihop_errors.append(
            (q["query_id"], "expected exactly two positive units")
        )
        continue

    numeric_values = []

    for r in positive:
        numbers = re.findall(
            r"\b\d+\b",
            r["gold_evidence_span"],
        )

        if numbers:
            numeric_values.append(
                int(numbers[0])
            )

    try:
        expected = int(q["gold_answer"])
    except ValueError:
        multihop_errors.append(
            (q["query_id"], "gold answer is not numeric")
        )
        continue

    if len(numeric_values) >= 2:
        if sum(numeric_values[:2]) != expected:
            multihop_errors.append(
                (
                    q["query_id"],
                    f"expected sum {expected}, "
                    f"observed {numeric_values[:2]}",
                )
            )

if multihop_errors:
    hard_errors.extend(
        f"{qid}: {reason}"
        for qid, reason in multihop_errors
    )

# ---------------------------------------------------------
# Conflict semantic distinction
# ---------------------------------------------------------
conflict_errors = []

for q in queries:
    if q["answerability"] != "conflict":
        continue

    positive = [
        r
        for r in qrels_by_query[q["query_id"]]
        if int(r["relevance_grade"]) > 0
    ]

    if len(positive) != 2:
        conflict_errors.append(
            (q["query_id"], "expected two positive conflict units")
        )
        continue

    text_a = positive[0]["gold_evidence_span"]
    text_b = positive[1]["gold_evidence_span"]

    # Conflict cases must not be identical.
    if text_a == text_b:
        conflict_errors.append(
            (q["query_id"], "conflict evidence texts identical")
        )

    # They should contain different numeric/time information.
    values_a = set(
        re.findall(
            r"\b\d+(?::\d{2})?\b",
            text_a,
        )
    )

    values_b = set(
        re.findall(
            r"\b\d+(?::\d{2})?\b",
            text_b,
        )
    )

    if values_a and values_b and values_a == values_b:
        conflict_errors.append(
            (q["query_id"], "conflict evidence has identical numeric/time values")
        )

if conflict_errors:
    hard_errors.extend(
        f"{qid}: {reason}"
        for qid, reason in conflict_errors
    )

# ---------------------------------------------------------
# Document template repetition
# ---------------------------------------------------------
unit_patterns = Counter()

for row in documents:
    text = row["text"].lower()

    text = re.sub(
        r"\b(?:cedar|maple|harbor|northstar|juniper|riverside)\b",
        "<entity>",
        text,
    )

    text = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        "<num>",
        text,
    )

    text = re.sub(
        r"\b\d{1,2}:\d{2}-\d{1,2}:\d{2}\b",
        "<time>",
        text,
    )

    text = re.sub(r"\s+", " ", text).strip()

    unit_patterns[text] += 1

top_unit_patterns = unit_patterns.most_common(10)

for pattern, count in top_unit_patterns:
    if count >= 30:
        warnings.append(
            f"DOCUMENT TEMPLATE REPETITION: {count}x [{pattern}]"
        )

# ---------------------------------------------------------
# Cross-query source evidence reuse
# ---------------------------------------------------------
evidence_by_query = {}

for qid, rows in qrels_by_query.items():
    evidence_by_query[qid] = {
        r["source_unit_id"]
        for r in rows
        if int(r["relevance_grade"]) > 0
    }

reuse_counts = Counter()

for units in evidence_by_query.values():
    for unit in units:
        reuse_counts[unit] += 1

# This is expected to some degree because each document has five queries.
# Report unusually concentrated reuse.
high_reuse = [
    (unit, count)
    for unit, count in reuse_counts.items()
    if count >= 5
]

if high_reuse:
    warnings.append(
        "EVIDENCE REUSE CONCENTRATION: "
        + ", ".join(
            f"{unit}={count}"
            for unit, count in high_reuse[:20]
        )
    )

# ---------------------------------------------------------
# Report
# ---------------------------------------------------------
REPORT.parent.mkdir(parents=True, exist_ok=True)

lines = []

lines.append("Aqlyra Tier A Semantic Quality Audit v0.3.2")
lines.append("=" * 52)
lines.append("")
lines.append(f"documents={len(documents)}")
lines.append(f"queries={len(queries)}")
lines.append(f"qrels={len(qrels)}")
lines.append("")

lines.append("QUERY TEMPLATE DIVERSITY")
lines.append(f"unique_normalized_templates={len(template_counts)}")
lines.append(
    f"templates_repeated_12plus={len(repeated_templates)}"
)
lines.append(
    f"cross_document_near_duplicates_ge_0.85={len(near_duplicates)}"
)
lines.append("")

lines.append("QREL / DISTRACTOR")
lines.append(
    f"distractor_gold_overlap_errors={distractor_errors}"
)
lines.append(
    f"direct_gold_answer_not_in_evidence={gold_answer_leaks}"
)
lines.append("")

lines.append("MULTI-HOP")
lines.append(
    f"multi_hop_errors={len(multihop_errors)}"
)
lines.append("")

lines.append("CONFLICT")
lines.append(
    f"conflict_errors={len(conflict_errors)}"
)
lines.append("")

lines.append("WARNINGS")
if warnings:
    for warning in warnings:
        lines.append(f"- {warning}")
else:
    lines.append("- none")

lines.append("")
lines.append("HARD ERRORS")
if hard_errors:
    for error in hard_errors:
        lines.append(f"- {error}")
else:
    lines.append("- none")

lines.append("")
lines.append("NEAR-DUPLICATE EXAMPLES")

for score, qid_a, qid_b in near_duplicates[:20]:
    lines.append(
        f"- {score:.3f}: {qid_a} <-> {qid_b}"
    )

lines.append("")
lines.append("TOP DOCUMENT TEMPLATES")

for pattern, count in top_unit_patterns[:10]:
    lines.append(
        f"- {count}x: {pattern}"
    )

lines.append("")
if hard_errors:
    decision = "REJECT_FOR_EXPERIMENT"
elif warnings:
    decision = "REVIEW_REQUIRED"
else:
    decision = "SEMANTIC_GATE_PASS"

lines.append(f"DECISION={decision}")

REPORT.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8",
)

print("\n".join(lines))

if hard_errors:
    raise SystemExit(1)
