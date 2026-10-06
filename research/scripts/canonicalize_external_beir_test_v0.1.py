from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

BASE = Path("research/benchmark_v0.3/external_v0.1")
RAW = BASE / "raw"
OUT = BASE / "canonical_test_v0.1"

if OUT.exists():
    raise SystemExit(
        f"REFUSING TO OVERWRITE EXISTING DIRECTORY: {OUT}"
    )

DATASETS = {
    "scifact": {
        "expected_queries": 300,
        "expected_qrels": 339,
        "expected_corpus": 5183,
    },
    "nfcorpus": {
        "expected_queries": 323,
        "expected_qrels": 12334,
        "expected_corpus": 3633,
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


OUT.mkdir(parents=True)

manifest = []

for dataset, expected in DATASETS.items():
    src = RAW / dataset
    dst = OUT / dataset
    dst.mkdir(parents=True)

    corpus_path = src / "corpus.jsonl"
    queries_path = src / "queries.jsonl"
    qrels_path = src / "qrels" / "test.tsv"

    corpus = load_jsonl(corpus_path)
    queries = load_jsonl(queries_path)

    with qrels_path.open(
        encoding="utf-8",
        newline=""
    ) as f:
        qrel_rows = list(csv.DictReader(f, delimiter="\t"))

    corpus_ids = {row["_id"] for row in corpus}
    all_query_ids = {row["_id"] for row in queries}
    test_query_ids = {row["query-id"] for row in qrel_rows}

    unknown_test_queries = test_query_ids - all_query_ids
    unknown_qrel_docs = {
        row["corpus-id"] for row in qrel_rows
    } - corpus_ids

    if unknown_test_queries:
        raise RuntimeError(
            f"{dataset}: test qrels reference unknown queries: "
            f"{sorted(unknown_test_queries)[:10]}"
        )

    if unknown_qrel_docs:
        raise RuntimeError(
            f"{dataset}: qrels reference unknown documents: "
            f"{sorted(unknown_qrel_docs)[:10]}"
        )

    if len(corpus) != expected["expected_corpus"]:
        raise RuntimeError(
            f"{dataset}: corpus={len(corpus)}, "
            f"expected={expected['expected_corpus']}"
        )

    if len(test_query_ids) != expected["expected_queries"]:
        raise RuntimeError(
            f"{dataset}: test queries={len(test_query_ids)}, "
            f"expected={expected['expected_queries']}"
        )

    if len(qrel_rows) != expected["expected_qrels"]:
        raise RuntimeError(
            f"{dataset}: qrels={len(qrel_rows)}, "
            f"expected={expected['expected_qrels']}"
        )

    # Preserve original corpus byte-for-byte.
    shutil.copy2(corpus_path, dst / "corpus.jsonl")

    # Select only queries referenced by test qrels, preserving
    # original queries.jsonl ordering.
    test_queries = [
        row for row in queries
        if row["_id"] in test_query_ids
    ]

    if len(test_queries) != len(test_query_ids):
        raise RuntimeError(
            f"{dataset}: test query selection is not one-to-one"
        )

    with (dst / "queries_test.jsonl").open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in test_queries:
            f.write(json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n")

    # Preserve official test qrels exactly.
    qrels_out = dst / "qrels_test.tsv"

    with qrels_out.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        writer = csv.writer(
            f,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writerow(["query-id", "corpus-id", "score"])

        for row in qrel_rows:
            writer.writerow([
                row["query-id"],
                row["corpus-id"],
                row["score"],
            ])

    # Dataset statistics.
    relevant_docs = {
        row["corpus-id"]
        for row in qrel_rows
        if float(row["score"]) > 0
    }

    score_counts = {}
    for row in qrel_rows:
        score = row["score"]
        score_counts[score] = score_counts.get(score, 0) + 1

    manifest.append({
        "dataset": dataset,
        "corpus_documents": len(corpus),
        "raw_queries": len(queries),
        "test_queries": len(test_query_ids),
        "test_qrels": len(qrel_rows),
        "unique_relevant_documents": len(relevant_docs),
        "qrel_score_distribution": json.dumps(
            score_counts,
            sort_keys=True,
        ),
        "corpus_sha256": sha256(corpus_path),
        "queries_test_sha256": sha256(
            dst / "queries_test.jsonl"
        ),
        "qrels_test_sha256": sha256(qrels_out),
    })

    print(f"\n[{dataset.upper()}]")
    print(f"corpus documents:       {len(corpus)}")
    print(f"raw queries:            {len(queries)}")
    print(f"test queries:           {len(test_query_ids)}")
    print(f"test qrels:             {len(qrel_rows)}")
    print(f"unique relevant docs:   {len(relevant_docs)}")
    print("qrel references:        PASS")
    print("test subset selection:  PASS")

manifest_path = OUT / "EXTERNAL_TEST_MANIFEST_v0.1.csv"

fields = [
    "dataset",
    "corpus_documents",
    "raw_queries",
    "test_queries",
    "test_qrels",
    "unique_relevant_documents",
    "qrel_score_distribution",
    "corpus_sha256",
    "queries_test_sha256",
    "qrels_test_sha256",
]

with manifest_path.open(
    "w",
    newline="",
    encoding="utf-8",
) as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(manifest)

print("\n=== EXTERNAL TEST CANONICALIZATION GATE ===")
print("SciFact:              PASS")
print("NFCorpus:             PASS")
print("Test query filtering: PASS")
print("QREL preservation:    PASS")
print("Corpus preservation:  PASS")
print("SHA-256 manifest:     PASS")
print("\nCANONICAL EXTERNAL TEST SET = PASS")
print(f"Manifest: {manifest_path}")
