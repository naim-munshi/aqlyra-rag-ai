"""Real Granite retrieval benchmark on versioned PUBLIC synthetic evidence only.

Does not connect to Aqlyra production services, private user documents,
database or embedding secrets. This is an OFFLINE dense-only evaluation,
not a production RAG quality/latency measurement.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np
from sentence_transformers import SentenceTransformer

from app.chunking import ChunkSource, build_chunks

ROOT = Path(__file__).resolve().parents[1]
MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
# Reviewed public model snapshot. Do not silently change model weights.
REVISION = "835ad14087e140460703cf0fae09f97d469d65c2"


def _load():
    corpus_dir = ROOT / "evaluation" / "corpus"
    dataset_path = ROOT / "evaluation" / "retrieval_cases.json"
    spec = json.loads(dataset_path.read_text(encoding="utf-8"))
    if len(spec["cases"]) != 20:
        raise RuntimeError("Golden-case count changed: review labels first")
    files = sorted(corpus_dir.glob("*.md"))
    if len(files) != 10:
        raise RuntimeError("Corpus size changed: review synthetic dataset first")

    chunks, digests = [], {}
    for file in files:
        text = file.read_text(encoding="utf-8")
        digests[file.name] = sha256(text.encode("utf-8")).hexdigest()
        sources = [ChunkSource(
            document_id=file.name,
            document_label=file.name,
            unit_id=file.name + ":all",
            unit_index=0,
            unit_type="text",
            source_label=file.name,
            content=text,
        )]
        chunks.extend(c for c in build_chunks(sources) if c.chunk_role == "content")
    if not chunks:
        raise RuntimeError("No content chunks available")

    labels = []
    for case in spec["cases"]:
        matched = {
            i for i, chunk in enumerate(chunks)
            if chunk.document_id == case["document_filename"]
            and case["evidence_marker"] in chunk.content
        }
        if not matched:
            raise RuntimeError(
                "Evidence marker missing in generated chunks for "
                + case["query_id"]
            )
        labels.append(matched)
    return spec, files, chunks, labels, digests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec, files, chunks, labels, digests = _load()

    model = SentenceTransformer(MODEL, revision=REVISION, device="cpu")
    start = time.perf_counter()
    passage_embeddings = model.encode(
        [chunk.embedding_content for chunk in chunks],
        batch_size=8,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_embeddings = model.encode(
        [case["query"] for case in spec["cases"]],
        batch_size=8,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    encode_seconds = time.perf_counter() - start
    if passage_embeddings.shape[1] != 384 or query_embeddings.shape[1] != 384:
        raise RuntimeError("Model dimension is not 384")
    if not np.isfinite(passage_embeddings).all() or not np.isfinite(query_embeddings).all():
        raise RuntimeError("Non-finite real vectors")
    scores = query_embeddings @ passage_embeddings.T
    metrics = {}
    samples = []
    for k in (1, 3, 5):
        hit_sum = precision_sum = recall_sum = reciprocal_sum = 0.0
        for idx, relevant in enumerate(labels):
            ranking = np.argsort(-scores[idx], kind="stable").tolist()[:k]
            matching = [rank + 1 for rank, chunk_index in enumerate(ranking) if chunk_index in relevant]
            hit_sum += float(bool(matching))
            precision_sum += len(matching) / k
            recall_sum += len(matching) / len(relevant)
            reciprocal_sum += (1.0 / matching[0]) if matching else 0.0
        n = len(labels)
        metrics[str(k)] = {
            "hit_rate": hit_sum / n,
            "precision": precision_sum / n,
            "recall": recall_sum / n,
            "mrr": reciprocal_sum / n,
        }
    for idx, case in enumerate(spec["cases"]):
        top = np.argsort(-scores[idx], kind="stable").tolist()[:5]
        samples.append({
            "query_id": case["query_id"],
            "gold_doc": case["document_filename"],
            "top5_chunk_ids": [chunks[i].id for i in top],
            "gold_retrieved_at_5": any(i in labels[idx] for i in top),
        })
    report = {
        "status": "measured_real_embeddings_offline_synthetic",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "revision": REVISION,
        "dimension": 384,
        "retrieval": "cosine_dense_only_numpy_no_postgres",
        "dataset": "20 English synthetic labeled cases; 10 synthetic Markdown documents",
        "documents": len(files),
        "chunks": len(chunks),
        "queries": len(labels),
        "sha256_corpus": digests,
        "encode_seconds_ci_cpu": round(encode_seconds, 3),
        "metrics": metrics,
        "per_query": samples,
        "limitations": [
            "Synthetic English labels only; no multilingual quality claim.",
            "Offline dense cosine retrieval; not live pgvector, hybrid RRF or production accuracy.",
            "Different chunk creation scope from historical seeded database; do not compare historical numbers directly.",
            "No secrets, personal data, user account or production backend contacted.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("status","model","documents","chunks","queries","metrics")}, indent=2))


if __name__ == "__main__":
    main()
