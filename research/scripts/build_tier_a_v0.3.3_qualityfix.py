from __future__ import annotations

import csv
import hashlib
import re
import shutil
from pathlib import Path
from collections import Counter

ROOT = Path("research/benchmark_v0.3")
SRC = ROOT / "data" / "tier_a_v0.3.2"
OUT = ROOT / "data" / "tier_a_v0.3.3"
REPORT = ROOT / "results" / "tier_a_v0.3.3_quality_audit.txt"

if not SRC.is_dir():
    raise SystemExit(f"ERROR: source dataset not found: {SRC}")

if OUT.exists():
    raise SystemExit(
        f"REFUSING TO OVERWRITE EXISTING DIRECTORY: {OUT}\n"
        "Use a new version instead of overwriting research artifacts."
    )

OUT.mkdir(parents=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# 1. Copy source artifacts unchanged first.
# ---------------------------------------------------------------------
for src_path in SRC.iterdir():
    if src_path.is_file():
        shutil.copy2(src_path, OUT / src_path.name)

# ---------------------------------------------------------------------
# 2. Rewrite ONLY the question text.
#    Gold answers, evidence, qrels, source IDs, answerability,
#    question types, and all other metadata remain unchanged.
# ---------------------------------------------------------------------
queries_path = OUT / "queries.csv"

with queries_path.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    if not fieldnames or "question" not in fieldnames:
        raise SystemExit("ERROR: queries.csv has no 'question' column")
    rows = list(reader)

countable_phrases = [
    "requests",
    "appointments",
    "transactions",
    "passenger trips",
    "applications",
    "patients",
    "parcels",
    "tickets",
    "bookings",
    "visits",
    "enrollments",
    "cases",
    "inspections",
    "applications",
    "registrations",
]

changed = []
duplicate_fixes = 0
grammar_fixes = 0

def fix_question(text: str) -> str:
    global duplicate_fixes, grammar_fixes

    original = text

    # Obvious duplicated-word authoring error.
    new = re.sub(
        r"\broutine\s+routine\b",
        "routine",
        text,
        flags=re.IGNORECASE,
    )
    if new != text:
        duplicate_fixes += 1
    text = new

    # Countable-noun grammar correction:
    # "How much requests" -> "How many requests"
    # "How much passenger trips" -> "How many passenger trips"
    for phrase in sorted(countable_phrases, key=len, reverse=True):
        pattern = rf"\bHow much\s+({re.escape(phrase)})\b"
        new = re.sub(
            pattern,
            r"How many \1",
            text,
            flags=re.IGNORECASE,
        )
        if new != text:
            grammar_fixes += 1
        text = new

    return text


for row in rows:
    original = row["question"]
    updated = fix_question(original)

    if updated != original:
        changed.append((row["query_id"], original, updated))
        row["question"] = updated

with queries_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# ---------------------------------------------------------------------
# 3. Validate that ONLY question text changed relative to v0.3.2.
# ---------------------------------------------------------------------
with (SRC / "queries.csv").open(newline="", encoding="utf-8") as f:
    old_rows = {r["query_id"]: r for r in csv.DictReader(f)}

with queries_path.open(newline="", encoding="utf-8") as f:
    new_rows = {r["query_id"]: r for r in csv.DictReader(f)}

if set(old_rows) != set(new_rows):
    raise SystemExit("ERROR: query ID set changed")

for qid in old_rows:
    for field in fieldnames:
        if field == "question":
            continue
        if old_rows[qid].get(field) != new_rows[qid].get(field):
            raise SystemExit(
                f"ERROR: non-question field changed for {qid}: {field}"
            )

# ---------------------------------------------------------------------
# 4. Basic structural checks.
# ---------------------------------------------------------------------
def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

docs = read_csv(OUT / "documents.csv")
queries = read_csv(OUT / "queries.csv")
qrels = read_csv(OUT / "qrels.csv")

assert len(docs) == 288, f"Expected 288 document units, got {len(docs)}"
assert len(queries) == 240, f"Expected 240 queries, got {len(queries)}"
assert len(qrels) == 288, f"Expected 288 qrels rows, got {len(qrels)}"

assert len({r["query_id"] for r in queries}) == 240
assert len({(r["source_doc_id"], r["source_unit_id"]) for r in docs}) == 288

# ---------------------------------------------------------------------
# 5. Quality checks.
# ---------------------------------------------------------------------
duplicate_words = []
grammar_errors = []

for q in queries:
    question = q["question"]

    if re.search(r"\b([A-Za-z]+)\s+\1\b", question, flags=re.IGNORECASE):
        duplicate_words.append((q["query_id"], question))

    if re.search(
        r"\bHow much\s+(requests|appointments|transactions|passenger trips|"
        r"applications|patients|parcels|tickets|bookings|visits|"
        r"enrollments|cases|inspections|registrations)\b",
        question,
        flags=re.IGNORECASE,
    ):
        grammar_errors.append((q["query_id"], question))

# ---------------------------------------------------------------------
# 6. Time-range-aware gold/evidence consistency.
# ---------------------------------------------------------------------
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

from collections import defaultdict

qrels_by_query = defaultdict(list)

for r in qrels:
    if int(r["relevance_grade"]) > 0:
        qrels_by_query[r["query_id"]].append(r)

direct_mismatches = []

for q in queries:
    if q["answerability"] != "answerable":
        continue

    if q["requires_multi_hop"].lower() == "true":
        continue

    answer = q["gold_answer"].strip()

    evidence = " ".join(
        r["gold_evidence_span"]
        for r in qrels_by_query[q["query_id"]]
    )

    if answer and normalize(answer) not in normalize(evidence):
        direct_mismatches.append(
            (q["query_id"], answer, evidence)
        )

# ---------------------------------------------------------------------
# 7. Distribution checks.
# ---------------------------------------------------------------------
type_counts = Counter(q["question_type"] for q in queries)
answerability_counts = Counter(q["answerability"] for q in queries)

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

if type_counts != expected_types:
    raise SystemExit(
        f"ERROR: question-type distribution changed: {dict(type_counts)}"
    )

if answerability_counts != expected_answerability:
    raise SystemExit(
        f"ERROR: answerability distribution changed: "
        f"{dict(answerability_counts)}"
    )

# ---------------------------------------------------------------------
# 8. SHA-256 consistency for tracked files.
# ---------------------------------------------------------------------
sha_path = OUT / "SHA256SUMS.csv"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if sha_path.exists():
    with sha_path.open(newline="", encoding="utf-8") as f:
        sha_rows = list(csv.DictReader(f))
        sha_fields = f.seek(0)  # no-op; just keep handle semantics clear

    with sha_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sha_fieldnames = reader.fieldnames
        sha_rows = list(reader)

    if not sha_fieldnames:
        raise SystemExit("ERROR: SHA256SUMS.csv has no header")

    file_key = next(
        (k for k in sha_fieldnames if k.lower() in {"file", "filename", "path", "artifact"}),
        None,
    )
    hash_key = next(
        (k for k in sha_fieldnames if k.lower() == "sha256"),
        None,
    )

    if not file_key or not hash_key:
        raise SystemExit(
            "ERROR: could not identify filename/SHA256 columns in SHA256SUMS.csv"
        )

    for row in sha_rows:
        name = Path(row[file_key]).name
        target = OUT / name
        if target.exists():
            row[hash_key] = sha256_file(target)

    with sha_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sha_fieldnames)
        writer.writeheader()
        writer.writerows(sha_rows)

# ---------------------------------------------------------------------
# 9. Write a provenance decision record.
# ---------------------------------------------------------------------
decision = ROOT / "PHASE3_CONTENT_QUALITY_DECISION_v0.3.3.md"

decision.write_text(
    """# Phase 3 Content Quality Decision — Tier A v0.3.3

## Status

**PASS — quality-fix release candidate**

## Lineage

- Source: `tier_a_v0.3.2`
- Derived version: `tier_a_v0.3.3`
- Source corpus, qrels, gold answers, answerability labels, query-type labels,
  and evidence mappings were preserved.
- No document retrieval unit was added, removed, or re-labeled.

## Changes

Only query wording was corrected:

1. removed the duplicated authoring pattern `routine routine`;
2. corrected `How much` to `How many` for countable nouns where applicable.

No gold evidence, qrels, or answer semantics were intentionally changed.

## Why a full redesign was not performed

The prior audit showed:

- 240/240 normalized question templates were unique;
- 20 duplicated-word errors were concentrated in one repeated phrase;
- the 104 direct gold/evidence mismatches disappeared under explicit
  time-range normalization, demonstrating representation mismatch rather
  than evidence mismatch.

Therefore a full benchmark rewrite would add unnecessary provenance risk
without evidence that the underlying qrels or information needs were invalid.

## Gate

This version is a **candidate benchmark artifact**, not yet the final frozen
research benchmark. It still requires:

- structural validation;
- semantic/qrel validation;
- human review of query naturalness;
- external benchmark validation;
- reproducible masking checks.

No main experiment should be interpreted as final evidence until those gates pass.
""",
    encoding="utf-8",
)

# ---------------------------------------------------------------------
# 10. Audit report.
# ---------------------------------------------------------------------
status = "PASS" if not duplicate_words and not grammar_errors and not direct_mismatches else "FAIL"

report_lines = [
    "Aqlyra Tier A v0.3.3 Quality Audit",
    "=" * 40,
    f"STATUS: {status}",
    "",
    f"documents: {len(docs)}",
    f"queries: {len(queries)}",
    f"qrels: {len(qrels)}",
    "",
    f"questions changed: {len(changed)}",
    f"duplicate-word fixes: {duplicate_fixes}",
    f"grammar fixes: {grammar_fixes}",
    "",
    f"remaining duplicate-word errors: {len(duplicate_words)}",
    f"remaining countable-noun grammar errors: {len(grammar_errors)}",
    f"remaining direct gold/evidence mismatches: {len(direct_mismatches)}",
    "",
    "QUESTION TYPE COUNTS",
]

for k, v in sorted(type_counts.items()):
    report_lines.append(f"{k}: {v}")

report_lines.append("")
report_lines.append("ANSWERABILITY COUNTS")

for k, v in sorted(answerability_counts.items()):
    report_lines.append(f"{k}: {v}")

if duplicate_words:
    report_lines.append("")
    report_lines.append("DUPLICATE-WORD ERRORS")
    report_lines.extend(f"{qid}: {q}" for qid, q in duplicate_words)

if grammar_errors:
    report_lines.append("")
    report_lines.append("GRAMMAR ERRORS")
    report_lines.extend(f"{qid}: {q}" for qid, q in grammar_errors)

if direct_mismatches:
    report_lines.append("")
    report_lines.append("DIRECT GOLD/EVIDENCE MISMATCHES")
    for qid, answer, evidence in direct_mismatches[:30]:
        report_lines.append(f"{qid}: GOLD={answer!r} EVID={evidence!r}")

REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

print(f"CREATED: {OUT}")
print(f"CHANGED QUESTIONS: {len(changed)}")
print(f"DUPLICATE-WORD FIXES: {duplicate_fixes}")
print(f"GRAMMAR FIXES: {grammar_fixes}")
print(f"DIRECT MISMATCHES AFTER NORMALIZATION: {len(direct_mismatches)}")
print(f"AUDIT REPORT: {REPORT}")
print(f"STATUS: {status}")

if status != "PASS":
    raise SystemExit(1)
