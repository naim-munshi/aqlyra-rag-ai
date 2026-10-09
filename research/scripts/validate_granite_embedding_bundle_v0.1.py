from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = (
    REPO_ROOT
    / "research"
    / "experiments"
    / "generated"
    / "tier_a_v0.3.3_granite_v0.1.npz"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "research"
    / "experiments"
    / "generated"
    / "tier_a_v0.3.3_granite_v0.1.json"
)
DIMENSION = 384


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not BUNDLE_PATH.is_file():
        raise SystemExit(f"Missing bundle: {BUNDLE_PATH}")

    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"Missing manifest: {MANIFEST_PATH}")

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    with np.load(BUNDLE_PATH, allow_pickle=False) as data:
        document_ids = data["document_ids"]
        document_embeddings = data["document_embeddings"]
        query_ids = data["query_ids"]
        query_embeddings = data["query_embeddings"]

    if document_embeddings.shape != (
        len(document_ids),
        DIMENSION,
    ):
        raise SystemExit(
            f"Invalid document shape: {document_embeddings.shape}"
        )

    if query_embeddings.shape != (
        len(query_ids),
        DIMENSION,
    ):
        raise SystemExit(
            f"Invalid query shape: {query_embeddings.shape}"
        )

    if len(set(document_ids.tolist())) != len(document_ids):
        raise SystemExit("Duplicate document IDs in bundle.")

    if len(set(query_ids.tolist())) != len(query_ids):
        raise SystemExit("Duplicate query IDs in bundle.")

    if not np.isfinite(document_embeddings).all():
        raise SystemExit("Non-finite document embeddings.")

    if not np.isfinite(query_embeddings).all():
        raise SystemExit("Non-finite query embeddings.")

    if not np.allclose(
        np.linalg.norm(document_embeddings, axis=1),
        1.0,
        atol=1e-5,
    ):
        raise SystemExit("Document embeddings fail normalization check.")

    if not np.allclose(
        np.linalg.norm(query_embeddings, axis=1),
        1.0,
        atol=1e-5,
    ):
        raise SystemExit("Query embeddings fail normalization check.")

    actual_bundle_hash = sha256_file(BUNDLE_PATH)
    expected_bundle_hash = (
        manifest["outputs"]["bundle_sha256"]
    )

    if actual_bundle_hash != expected_bundle_hash:
        raise SystemExit(
            "Bundle SHA-256 mismatch: "
            f"{actual_bundle_hash} != {expected_bundle_hash}"
        )

    if manifest["dimension"] != DIMENSION:
        raise SystemExit("Manifest dimension mismatch.")

    print("documents:", len(document_ids))
    print("queries:", len(query_ids))
    print("document shape:", document_embeddings.shape)
    print("query shape:", query_embeddings.shape)
    print("bundle sha256:", actual_bundle_hash)
    print("\nGRANITE BUNDLE VALIDATION: PASS")


if __name__ == "__main__":
    main()
