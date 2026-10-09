from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_ID = "ibm-granite/granite-embedding-97m-multilingual-r2"
REVISION = "c61e626a6255c490879d0af885078b61929d51f6"
DIMENSION = 384

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "research" / "benchmark_v0.3" / "data" / "tier_a_v0.3.3"
DOCUMENTS_PATH = DATA_ROOT / "documents.csv"
QUERIES_PATH = DATA_ROOT / "queries.csv"

GENERATED_ROOT = (
    REPO_ROOT
    / "research"
    / "experiments"
    / "generated"
)

BUNDLE_PATH = GENERATED_ROOT / "tier_a_v0.3.3_granite_v0.1.npz"
MANIFEST_PATH = GENERATED_ROOT / "tier_a_v0.3.3_granite_v0.1.json"

MODEL_PATH = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--ibm-granite--granite-embedding-97m-multilingual-r2"
    / "snapshots"
    / REVISION
)

ID_KEYS = (
    "unit_id",
    "source_unit_id",
    "chunk_id",
    "document_id",
    "doc_id",
    "query_id",
    "_id",
    "id",
)

DOCUMENT_TEXT_KEYS = (
    "content",
    "text",
    "document_text",
    "body",
)

QUERY_TEXT_KEYS = (
    "query_text",
    "question",
    "text",
    "query",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pick(row: dict[str, str], keys: tuple[str, ...], label: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    raise ValueError(
        f"No usable {label} field found. "
        f"Available columns: {sorted(row)}"
    )


def load_records(
    path: Path,
    text_keys: tuple[str, ...],
    label: str,
) -> tuple[list[str], list[str]]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"{label} CSV is empty: {path}")

    ids: list[str] = []
    texts: list[str] = []
    seen: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        record_id = pick(row, ID_KEYS, f"{label} ID")
        text = pick(row, text_keys, f"{label} text")

        if record_id in seen:
            raise ValueError(
                f"Duplicate {label} ID at CSV row {row_number}: {record_id}"
            )

        seen.add(record_id)
        ids.append(record_id)
        texts.append(text)

    return ids, texts


def main() -> None:
    print("=== GRANITE BUNDLE BUILD ===")
    print("Repository:", REPO_ROOT)
    print("Documents:", DOCUMENTS_PATH)
    print("Queries:", QUERIES_PATH)
    print("Model:", MODEL_ID)
    print("Revision:", REVISION)

    if not MODEL_PATH.is_dir():
        raise SystemExit(f"Missing pinned local model snapshot: {MODEL_PATH}")

    document_ids, document_texts = load_records(
        DOCUMENTS_PATH,
        DOCUMENT_TEXT_KEYS,
        "document",
    )

    query_ids, query_texts = load_records(
        QUERIES_PATH,
        QUERY_TEXT_KEYS,
        "query",
    )

    print("documents:", len(document_ids))
    print("queries:", len(query_ids))

    print("\n=== LOAD LOCAL MODEL ===")
    model = SentenceTransformer(str(MODEL_PATH), device="cpu")

    dimension = model.get_sentence_embedding_dimension()
    print("dimension:", dimension)

    if dimension != DIMENSION:
        raise SystemExit(
            f"Unexpected embedding dimension: {dimension}; expected {DIMENSION}"
        )

    print("\n=== ENCODE DOCUMENTS ===")
    document_embeddings = model.encode(
        document_texts,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(np.float32, copy=False)

    print("document shape:", document_embeddings.shape)

    print("\n=== ENCODE QUERIES ===")
    query_embeddings = model.encode(
        query_texts,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(np.float32, copy=False)

    print("query shape:", query_embeddings.shape)

    expected_document_shape = (len(document_ids), DIMENSION)
    expected_query_shape = (len(query_ids), DIMENSION)

    if document_embeddings.shape != expected_document_shape:
        raise SystemExit(
            f"Unexpected document embedding shape: "
            f"{document_embeddings.shape}; expected {expected_document_shape}"
        )

    if query_embeddings.shape != expected_query_shape:
        raise SystemExit(
            f"Unexpected query embedding shape: "
            f"{query_embeddings.shape}; expected {expected_query_shape}"
        )

    if not np.isfinite(document_embeddings).all():
        raise SystemExit("Document embeddings contain non-finite values.")

    if not np.isfinite(query_embeddings).all():
        raise SystemExit("Query embeddings contain non-finite values.")

    document_norms = np.linalg.norm(document_embeddings, axis=1)
    query_norms = np.linalg.norm(query_embeddings, axis=1)

    if not np.allclose(document_norms, 1.0, atol=1e-5):
        raise SystemExit("Document embeddings are not L2-normalized.")

    if not np.allclose(query_norms, 1.0, atol=1e-5):
        raise SystemExit("Query embeddings are not L2-normalized.")

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        BUNDLE_PATH,
        document_ids=np.asarray(document_ids, dtype=str),
        document_embeddings=document_embeddings,
        query_ids=np.asarray(query_ids, dtype=str),
        query_embeddings=query_embeddings,
    )

    manifest = {
        "status": "verified",
        "dataset": "tier_a_v0.3.3_candidate",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "dimension": DIMENSION,
        "similarity": "cosine",
        "normalization": "L2",
        "documents": len(document_ids),
        "queries": len(query_ids),
        "embedding_dtype": "float32",
        "inputs": {
            "documents_csv": str(DOCUMENTS_PATH.relative_to(REPO_ROOT)),
            "documents_sha256": sha256_file(DOCUMENTS_PATH),
            "queries_csv": str(QUERIES_PATH.relative_to(REPO_ROOT)),
            "queries_sha256": sha256_file(QUERIES_PATH),
        },
        "outputs": {
            "bundle": str(BUNDLE_PATH.relative_to(REPO_ROOT)),
            "bundle_sha256": None,
        },
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest["outputs"]["bundle_sha256"] = sha256_file(BUNDLE_PATH)

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== BUILD RESULT ===")
    print("bundle:", BUNDLE_PATH)
    print("manifest:", MANIFEST_PATH)
    print("bundle sha256:", manifest["outputs"]["bundle_sha256"])
    print("\nGRANITE BUNDLE BUILD: PASS")


if __name__ == "__main__":
    main()
