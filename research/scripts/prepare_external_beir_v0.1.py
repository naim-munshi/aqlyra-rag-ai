from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

BASE = Path("research/benchmark_v0.3/external_v0.1")
RAW = BASE / "raw"
MANIFEST = BASE / "manifest"

DATASETS = {
    "scifact": {
        "md5": "5f7d1de60b170fc8027bb7898e2efca1",
        "archive": RAW / "scifact.zip",
    },
    "nfcorpus": {
        "md5": "a89dba18a62ef92f7d323ec890a0d38d",
        "archive": RAW / "nfcorpus.zip",
    },
}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()

    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(destination)):
                raise RuntimeError(
                    f"Unsafe archive member detected: {member.filename}"
                )

        z.extractall(destination)


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


summary = []

for name, cfg in DATASETS.items():
    archive = cfg["archive"]
    root = RAW / name

    print(f"\n=== {name.upper()} ===")

    if not archive.exists():
        raise RuntimeError(f"Missing archive: {archive}")

    actual_md5 = md5(archive)
    expected_md5 = cfg["md5"]

    print(f"MD5 actual:   {actual_md5}")
    print(f"MD5 expected: {expected_md5}")

    if actual_md5 != expected_md5:
        raise RuntimeError(f"{name}: MD5 verification failed")

    if not root.exists():
        print("EXTRACTING...")
        safe_extract(archive, RAW)
    else:
        print(f"Directory already exists: {root}")

    corpus_path = root / "corpus.jsonl"
    queries_path = root / "queries.jsonl"
    qrels_path = root / "qrels" / "test.tsv"

    required = [corpus_path, queries_path, qrels_path]

    for path in required:
        if not path.exists():
            raise RuntimeError(f"{name}: missing required file: {path}")

    corpus = load_jsonl(corpus_path)
    queries = load_jsonl(queries_path)

    with qrels_path.open(
        encoding="utf-8",
        newline=""
    ) as f:
        qrels = list(csv.DictReader(f, delimiter="\t"))

    corpus_ids = [x["_id"] for x in corpus]
    query_ids = [x["_id"] for x in queries]

    corpus_id_set = set(corpus_ids)
    query_id_set = set(query_ids)

    if len(corpus_ids) != len(corpus_id_set):
        raise RuntimeError(f"{name}: duplicate corpus IDs")

    if len(query_ids) != len(query_id_set):
        raise RuntimeError(f"{name}: duplicate query IDs")

    unknown_queries = sorted(
        {r["query-id"] for r in qrels} - query_id_set
    )

    unknown_docs = sorted(
        {r["corpus-id"] for r in qrels} - corpus_id_set
    )

    if unknown_queries:
        raise RuntimeError(
            f"{name}: qrels reference unknown queries: "
            f"{unknown_queries[:10]}"
        )

    if unknown_docs:
        raise RuntimeError(
            f"{name}: qrels reference unknown corpus IDs: "
            f"{unknown_docs[:10]}"
        )

    item = {
        "dataset": name,
        "corpus": len(corpus),
        "queries": len(queries),
        "qrels": len(qrels),
        "unique_corpus_ids": len(corpus_id_set),
        "unique_query_ids": len(query_id_set),
        "unknown_qrel_queries": len(unknown_queries),
        "unknown_qrel_docs": len(unknown_docs),
        "archive_md5": actual_md5,
        "archive_sha256": sha256(archive),
    }

    summary.append(item)

    print(f"corpus:            {item['corpus']}")
    print(f"queries:           {item['queries']}")
    print(f"qrels:             {item['qrels']}")
    print(f"unique corpus IDs: {item['unique_corpus_ids']}")
    print(f"unique query IDs:  {item['unique_query_ids']}")
    print("qrel references:   PASS")

inventory_path = MANIFEST / "EXTERNAL_DATASET_INVENTORY_v0.1.csv"

fields = [
    "dataset",
    "corpus",
    "queries",
    "qrels",
    "unique_corpus_ids",
    "unique_query_ids",
    "unknown_qrel_queries",
    "unknown_qrel_docs",
    "archive_md5",
    "archive_sha256",
]

with inventory_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(summary)

sha_path = MANIFEST / "RAW_ARCHIVE_SHA256.txt"

with sha_path.open("w", encoding="utf-8") as f:
    for item in summary:
        f.write(
            f"{item['archive_sha256']}  "
            f"raw/{item['dataset']}.zip\n"
        )

print("\n=== EXTERNAL RAW DATA GATE ===")
print("SciFact archive:       PASS")
print("NFCorpus archive:      PASS")
print("Archive MD5:            PASS")
print("Archive SHA-256:        PASS")
print("Corpus/query IDs:       PASS")
print("QREL references:        PASS")
print("\nEXTERNAL RAW DATA GATE = PASS")
print(f"Inventory: {inventory_path}")
print(f"SHA256:    {sha_path}")
