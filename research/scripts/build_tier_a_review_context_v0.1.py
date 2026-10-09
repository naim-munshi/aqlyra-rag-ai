from __future__ import annotations

import ast
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research/benchmark_v0.3/data/tier_a_v0.3.3"
REVIEW = ROOT / "research/benchmark_v0.3/review_v0.1"

QUERIES = DATA / "queries.csv"
DOCS = DATA / "documents.csv"
QRELS = DATA / "qrels.csv"
PACKET = REVIEW / "tier_a_v0.3.3_human_review_packet_v0.1.csv"

OUT_JSONL = REVIEW / "tier_a_v0.3.3_human_review_context_v0.1.jsonl"
OUT_MD = REVIEW / "HUMAN_REVIEW_INSTRUCTIONS_v0.1.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_ids(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass

    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass

    if ";" in value:
        return [x.strip() for x in value.split(";") if x.strip()]

    if "," in value:
        return [x.strip() for x in value.split(",") if x.strip()]

    return [value]


queries = read_csv(QUERIES)
docs = read_csv(DOCS)
qrels = read_csv(QRELS)
packet = read_csv(PACKET)

doc_by_unit = {
    r["source_unit_id"]: r
    for r in docs
}

qrels_by_query: dict[str, list[dict[str, str]]] = {}

for row in qrels:
    qrels_by_query.setdefault(row["query_id"], []).append(row)

packet_ids = {r["query_id"] for r in packet}

records = []

for q in packet:
    qid = q["query_id"]

    gold_rows = qrels_by_query.get(qid, [])

    gold_units = []
    for r in gold_rows:
        uid = r["source_unit_id"]
        doc = doc_by_unit.get(uid)

        if doc is None:
            raise SystemExit(
                f"{qid}: qrel references missing unit {uid}"
            )

        gold_units.append(
            {
                "source_unit_id": uid,
                "source_doc_id": r["source_doc_id"],
                "document_version": r["document_version"],
                "relevance_grade": r["relevance_grade"],
                "conflicting_unit_flag": r["conflicting_unit_flag"],
                "conflict_group_id": r["conflict_group_id"],
                "gold_evidence_span": r["gold_evidence_span"],
                "annotation_notes": r["annotation_notes"],
                "text": doc["text"],
            }
        )

    distractor_ids = parse_ids(q["distractor_unit_ids"])

    distractor_units = []

    for uid in distractor_ids:
        doc = doc_by_unit.get(uid)

        if doc is None:
            raise SystemExit(
                f"{qid}: unknown distractor unit {uid}"
            )

        distractor_units.append(
            {
                "source_unit_id": uid,
                "source_doc_id": doc["source_doc_id"],
                "document_version": doc["document_version"],
                "text": doc["text"],
            }
        )

    records.append(
        {
            "query_id": qid,
            "question": q["question"],
            "question_type": q["question_type"],
            "answerability": q["answerability"],
            "gold_answer": q["gold_answer"],
            "scope_id": q["scope_id"],
            "conflict_group_id": q["conflict_group_id"],
            "resolution_rule": q["resolution_rule"],
            "gold_evidence_count": int(q["gold_evidence_count"]),
            "requires_multi_hop": (
                q["requires_multi_hop"].strip().lower() == "true"
            ),
            "lexical_overlap_bucket": q["lexical_overlap_bucket"],
            "distractor_unit_count": int(q["distractor_unit_count"]),
            "gold_evidence_units": gold_units,
            "distractor_units": distractor_units,
            "reviewer_decision": "",
            "gold_answer_ok": "",
            "gold_evidence_ok": "",
            "qrels_ok": "",
            "answerability_ok": "",
            "multi_hop_ok": "",
            "conflict_ok": "",
            "distractor_ok": "",
            "reviewer_notes": "",
        }
    )


if {r["query_id"] for r in records} != packet_ids:
    raise SystemExit("Packet/context query ID mismatch")

with OUT_JSONL.open("w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


OUT_MD.write_text(
"""# Tier-A v0.3.3 Human Review Instructions v0.1

## Status

This is a human-review instrument for the machine-generated
120-query review sample.

The benchmark source files remain unchanged.

Do not change `queries.csv`, `documents.csv`, or `qrels.csv`
during review.

## Review decision

Use:

- `PASS` — annotation is supported by the supplied source text.
- `REVISE` — annotation has a correct underlying intent but requires a concrete correction.
- `REJECT` — query/evidence construction is materially invalid for evaluation.

## Review checks

For every query, independently inspect:

### 1. Question validity

Confirm that the question is grammatical, understandable,
specific enough to evaluate, and does not contain accidental
template artifacts.

### 2. Gold answer

For answerable queries:

- the gold answer must be supported by the gold evidence;
- it must answer the question directly;
- it must not introduce unsupported facts.

For unanswerable queries:

- the supplied corpus units must not contain sufficient evidence
  to establish the requested answer.

For conflict queries:

- the evidence must contain the intended conflicting information;
- the resolution rule must be understandable.

### 3. Gold evidence

For every gold evidence unit:

- the unit must materially support the answer or conflict;
- the highlighted evidence span must occur in the supplied text;
- no essential evidence unit should be missing.

### 4. Multi-hop

When `requires_multi_hop=true`, at least two distinct evidence
units must be necessary to derive the intended answer.

A query should not be labeled multi-hop merely because two units
happen to contain related information.

### 5. Conflict

For `answerability=conflict`:

- the qrels should identify the conflicting units;
- the units should actually present incompatible claims or values
  relevant to the question;
- the conflict-group metadata should be consistent.

### 6. Distractors

Distractor units must be legitimate corpus units and must not
already be gold evidence.

Check that distractors are plausibly confusing but do not
accidentally contain the intended answer.

## Reviewer fields

`reviewer_decision`
`gold_answer_ok`
`gold_evidence_ok`
`qrels_ok`
`answerability_ok`
`multi_hop_ok`
`conflict_ok`
`distractor_ok`
`reviewer_notes`

Use `yes/no` for the boolean fields.

Leave no reviewer field blank after reviewing a query.

## Important

A completed automated audit is not equivalent to human review.

The benchmark must not be described as human-frozen until the
selected queries have actually been reviewed and accepted.
""",
encoding="utf-8",
)

print("=== REVIEW CONTEXT BUILD ===")
print("packet queries:", len(packet))
print("context records:", len(records))
print("context:", OUT_JSONL)
print("instructions:", OUT_MD)

missing_gold_text = sum(
    1
    for r in records
    for u in r["gold_evidence_units"]
    if not u["text"].strip()
)

missing_distractor_text = sum(
    1
    for r in records
    for u in r["distractor_units"]
    if not u["text"].strip()
)

print("gold units with empty text:", missing_gold_text)
print("distractors with empty text:", missing_distractor_text)

if missing_gold_text or missing_distractor_text:
    raise SystemExit("REVIEW CONTEXT BUILD: FAIL")

print("REVIEW CONTEXT BUILD: PASS")
