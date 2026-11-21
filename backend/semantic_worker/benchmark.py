"""Read-only 512MiB production-weight semantic worker retrieval benchmark.

Uses actual pinned ONNX model and Aqlyra's own chunking against a PUBLIC,
synthetic ten-document English corpus with 20 EN + 20 JA + 20 BN labeled
queries. No Neon, production API, credentials or user document bytes.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from app.chunking import ChunkSource, build_chunks
from semantic_worker.model import DIMENSION, MODEL, REPO, REVISION, get_encoder


def build_cases(root: Path):
    cases_file = root / "retrieval_cases.json"
    translations_file = root / "retrieval_cases_cross_language.json"
    baseline = json.loads(cases_file.read_text(encoding="utf-8"))["cases"]
    translations = json.loads(translations_file.read_text(encoding="utf-8"))["translations"]
    if len(baseline) != 20 or len(translations) != 20:
        raise RuntimeError("Synthetic evaluation labels unexpectedly changed")
    translated = {r["query_id"]: r for r in translations}
    if len(translated) != 20 or set(translated) != {r["query_id"] for r in baseline}:
        raise RuntimeError("Cross-language label mismatch")
    files = sorted((root / "corpus").glob("*.md"))
    if len(files) != 10:
        raise RuntimeError("The public synthetic corpus changed")
    chunks = []
    digests = {}
    for path in files:
        content = path.read_text(encoding="utf-8")
        digests[path.name] = sha256(content.encode("utf-8")).hexdigest()
        src = ChunkSource(
            document_id=path.name, document_label=path.name,
            unit_id=path.name + ":all", unit_index=0,
            unit_type="text", source_label=path.name, content=content,
        )
        chunks.extend(c for c in build_chunks([src]) if c.chunk_role == "content")
    rows = []
    for case in baseline:
        relevance = [
            i for i, c in enumerate(chunks)
            if c.document_id == case["document_filename"]
            and case["evidence_marker"] in c.content
        ]
        if not relevance:
            raise RuntimeError("Missing labeled evidence marker for " + case["query_id"])
        for language, text in (
            ("en", case["query"]),
            ("ja", translated[case["query_id"]]["ja"]),
            ("bn", translated[case["query_id"]]["bn"]),
        ):
            if not isinstance(text, str) or len(text.strip()) < 8:
                raise RuntimeError("Invalid labeled query")
            rows.append({
                "query_id": case["query_id"], "lang": language, "query": text,
                "gold": set(relevance), "filename": case["document_filename"],
            })
    return chunks, rows, digests


def encode_in_batches(encoder, contents, mode: str):
    vectors = []
    for start in range(0, len(contents), 8):
        vectors.extend(encoder.encode(contents[start:start + 8], mode))
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != DIMENSION or not np.isfinite(matrix).all():
        raise RuntimeError("Invalid real ONNX vector shape or contents")
    return matrix


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("/app/evaluation"))
    p.add_argument("--output", type=Path, default=Path("/reports/static-384d-crosslang.json"))
    args = p.parse_args()
    chunks, rows, digests = build_cases(args.root)
    encoder = get_encoder()
    start = perf_counter()
    passage_vectors = encode_in_batches(
        encoder, [c.embedding_content for c in chunks], "passage"
    )
    query_vectors = encode_in_batches(encoder, [r["query"] for r in rows], "query")
    encode_seconds = perf_counter() - start
    similarities = query_vectors @ passage_vectors.T
    per_case = []
    for i, row in enumerate(rows):
        ranking = np.argsort(-similarities[i], kind="stable")
        rank = next(
            (k + 1 for k, j in enumerate(ranking) if int(j) in row["gold"]), None
        )
        per_case.append({
            "query_id": row["query_id"], "language": row["lang"],
            "expected_document": row["filename"],
            "top1_document": chunks[int(ranking[0])].document_id,
            "first_relevant_rank": rank,
        })
    scores = {}
    for language in ("en", "ja", "bn", "all"):
        selected = [x for x in per_case if language == "all" or x["language"] == language]
        n = len(selected)
        scores[language] = {
            "cases": n,
            "hit_at_1": round(sum(x["first_relevant_rank"] == 1 for x in selected) / n, 4),
            "hit_at_3": round(sum(x["first_relevant_rank"] is not None and x["first_relevant_rank"] <= 3 for x in selected) / n, 4),
            "hit_at_5": round(sum(x["first_relevant_rank"] is not None and x["first_relevant_rank"] <= 5 for x in selected) / n, 4),
            "mrr_at_5": round(sum(1/x["first_relevant_rank"] if x["first_relevant_rank"] and x["first_relevant_rank"] <= 5 else 0 for x in selected) / n, 4),
        }
    report = {
        "status": "verified_real_production_weight_static_384d_synthetic",
        "upstream_repo": REPO,
        "upstream_revision": REVISION,
        "model": MODEL, "dimension": DIMENSION,
        "documents": len(digests), "content_chunks": len(chunks),
        "queries": len(rows), "source_file_sha256": digests,
        "encode_seconds_ci_cpu": round(encode_seconds, 3),
        "scores_by_language": scores, "per_query": per_case,
        "limitations": [
            "Synthetic English source corpus; author-translated EN/JA/BN questions.",
            "Real ONNX model weights and existing chunking, but OFFLINE dense cosine only.",
            "Not production HTTP/pgvector/hybrid pipeline, answer generation, hallucination or user E2E.",
            "Run as disposable 512MiB container; no access to real private documents.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"model": MODEL, "revision": REVISION, "scores": scores}, indent=2))


if __name__ == "__main__":
    main()
