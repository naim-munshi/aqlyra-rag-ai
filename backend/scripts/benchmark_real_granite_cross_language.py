"""Reproducible real Granite cross-language retrieval; public synthetic data only.

English evidence remains in the original ten Markdown documents. Japanese
and Bengali queries are author-translated with query IDs referencing the
original exact evidence markers. Reports are retrieval scores, never answer
accuracy, and never touch Neon production data or user uploads.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.benchmark_real_granite_offline import MODEL, REVISION, ROOT, _load


def load_cross_language():
    spec, files, chunks, labels, digests = _load()
    path = ROOT / "evaluation" / "retrieval_cases_cross_language.json"
    raw = path.read_bytes()
    dataset = json.loads(raw)
    rows = dataset["translations"]
    expected = {item["query_id"]: (item, labels[i]) for i, item in enumerate(spec["cases"])}
    if len(rows) != 20 or len({item["query_id"] for item in rows}) != 20:
        raise RuntimeError("Unreviewed cross-language query count or duplicate label")
    if {item["query_id"] for item in rows} != set(expected):
        raise RuntimeError("Cross-language question IDs are not identical to baseline")
    cases = []
    for original, relevance in zip(spec["cases"], labels):
        cases.append({
            "query_id": original["query_id"], "language": "en",
            "query": original["query"], "gold": relevance,
            "source_doc": original["document_filename"],
        })
    for item in rows:
        baseline, relevance = expected[item["query_id"]]
        for language in ("ja", "bn"):
            text = item.get(language)
            if not isinstance(text, str) or len(text.strip()) < 8:
                raise RuntimeError("Unreviewed or empty multilingual query")
            cases.append({
                "query_id": item["query_id"], "language": language,
                "query": text.strip(), "gold": relevance,
                "source_doc": baseline["document_filename"],
            })
    return cases, chunks, files, digests, sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases, chunks, files, digests, labeled_digest = load_cross_language()
    model = SentenceTransformer(MODEL, revision=REVISION, device="cpu")
    started = time.perf_counter()
    passage_embeddings = model.encode(
        [chunk.embedding_content for chunk in chunks], batch_size=8,
        convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
    )
    query_embeddings = model.encode(
        [row["query"] for row in cases], batch_size=8,
        convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
    )
    duration = time.perf_counter() - started
    if passage_embeddings.shape[1] != 384 or query_embeddings.shape[1] != 384:
        raise RuntimeError("Unexpected Granite embedding dimension")
    if not np.isfinite(passage_embeddings).all() or not np.isfinite(query_embeddings).all():
        raise RuntimeError("Non-finite embeddings")
    similarity = query_embeddings @ passage_embeddings.T
    per_query = []
    for i, row in enumerate(cases):
        ranked = np.argsort(-similarity[i], kind="stable").tolist()
        relevant = set(row["gold"])
        first_rank = next((i + 1 for i, chunk_id in enumerate(ranked) if chunk_id in relevant), None)
        per_query.append({
            "query_id": row["query_id"],
            "language": row["language"],
            "expected_document": row["source_doc"],
            "top1_document": chunks[ranked[0]].document_id,
            "first_relevant_rank": first_rank,
            "hit_at_1": bool(first_rank == 1),
            "hit_at_3": bool(first_rank is not None and first_rank <= 3),
            "hit_at_5": bool(first_rank is not None and first_rank <= 5),
            "mrr_at_5": round(1.0 / first_rank, 6) if first_rank and first_rank <= 5 else 0.0,
        })
    scores = {}
    for language in ("en", "ja", "bn", "all"):
        subset = [x for x in per_query if x["language"] == language or language == "all"]
        n = len(subset)
        scores[language] = {
            "cases": n,
            "hit_at_1": round(sum(x["hit_at_1"] for x in subset) / n, 4),
            "hit_at_3": round(sum(x["hit_at_3"] for x in subset) / n, 4),
            "hit_at_5": round(sum(x["hit_at_5"] for x in subset) / n, 4),
            "mrr_at_5": round(sum(x["mrr_at_5"] for x in subset) / n, 4),
        }
    report = {
        "status": "measured_real_granite_cross_language_synthetic",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "model_revision": REVISION,
        "embedding_dimension": 384,
        "retrieval": "offline_dense_cosine_not_pgvector_not_hybrid",
        "documents": len(files), "chunks": len(chunks), "query_count": len(cases),
        "source_corpus_sha256": digests, "cross_language_dataset_sha256": labeled_digest,
        "encode_seconds_ci_cpu": round(duration, 3),
        "scores_by_query_language": scores, "per_query": per_query,
        "limitations": [
            "20 English, 20 Japanese, 20 Bengali author-translated synthetic queries over ten English documents.",
            "Cross-language retrieval only; independent human translation review is outstanding.",
            "Offline dense cosine results; not live production retrieval, hybrid ranking, answer grounding or latency.",
            "No threshold tuning; no negative unanswerable queries; no private user data used.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"model": MODEL, "documents": len(files), "chunks": len(chunks),
                      "queries": len(cases), "results": scores}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
