from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import psycopg
from huggingface_hub import HfApi

from app.config.settings import settings
from app.embeddings.huggingface_provider import (
    HuggingFaceEmbeddingProvider,
)

MODEL = "ibm-granite/granite-embedding-97m-multilingual-r2"
DB_URL = "postgresql://postgres:postgres@127.0.0.1:5434/aqlyra_rag_ai"

BATCH_SIZE = 16
MAX_RETRIES = 3
TIMEOUT_SECONDS = 180.0

OUTPUT = Path(
    "../research/granite_reproducibility_401_checkpoint.json"
)

if not settings.HF_TOKEN:
    raise RuntimeError("HF_TOKEN is not configured")

# Record exact current Hub revision.
info = HfApi(
    token=settings.HF_TOKEN
).model_info(MODEL)

print("===== MODEL PROVENANCE =====")
print("model =", info.id)
print("sha   =", info.sha)
print("task  =", info.pipeline_tag)
print("library =", info.library_name)
print()

provider = HuggingFaceEmbeddingProvider(
    token=settings.HF_TOKEN,
    model_name=MODEL,
    dimension=384,
    max_batch_size=BATCH_SIZE,
    timeout_seconds=TIMEOUT_SECONDS,
)

sql = """
SELECT
    er.id,
    er.chunk_id,
    dc.embedding_content,
    er.embedding::real[] AS stored_embedding,
    er.created_at
FROM embedding_records er
JOIN document_chunks dc
  ON dc.id = er.chunk_id
WHERE er.provider_name = 'huggingface'
  AND er.model_name = %s
ORDER BY er.created_at, er.id;
"""

with psycopg.connect(DB_URL) as conn:
    rows = conn.execute(sql, (MODEL,)).fetchall()

if len(rows) != 401:
    raise RuntimeError(
        f"Expected 401 Granite records, got {len(rows)}"
    )

if OUTPUT.exists():
    checkpoint = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )
    results = checkpoint.get("results", [])
else:
    results = []

completed_ids = {
    item["record_id"]
    for item in results
}

print("Total records   :", len(rows))
print("Already verified:", len(completed_ids))
print("Remaining       :", len(rows) - len(completed_ids))
print()

for start in range(0, len(rows), BATCH_SIZE):
    batch = [
        row
        for row in rows[start:start + BATCH_SIZE]
        if row[0] not in completed_ids
    ]

    if not batch:
        continue

    print(
        f"Processing records {start + 1}-"
        f"{min(start + BATCH_SIZE, len(rows))}"
    )

    texts = [row[2] for row in batch]

    vectors = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"  attempt {attempt}/{MAX_RETRIES}"
            )

            vectors = provider.embed_documents(texts)
            break

        except Exception as exc:
            print(
                f"  {type(exc).__name__}: {exc}"
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(5 * attempt)

    if vectors is None:
        raise RuntimeError("No embeddings returned")

    for row, reproduced in zip(batch, vectors):
        stored = np.asarray(
            row[3],
            dtype=np.float64,
        )

        reproduced = np.asarray(
            reproduced,
            dtype=np.float64,
        )

        if stored.shape != reproduced.shape:
            raise RuntimeError(
                f"Dimension mismatch: {row[1]}"
            )

        stored_norm = np.linalg.norm(stored)
        reproduced_norm = np.linalg.norm(reproduced)

        cosine = float(
            np.dot(stored, reproduced)
            / (
                stored_norm
                * reproduced_norm
            )
        )

        max_abs = float(
            np.max(
                np.abs(
                    stored - reproduced
                )
            )
        )

        mean_abs = float(
            np.mean(
                np.abs(
                    stored - reproduced
                )
            )
        )

        l2 = float(
            np.linalg.norm(
                stored - reproduced
            )
        )

        results.append({
            "record_id": row[0],
            "chunk_id": row[1],
            "created_at": row[4].isoformat(),
            "cosine": cosine,
            "max_abs": max_abs,
            "mean_abs": mean_abs,
            "l2": l2,
        })

        completed_ids.add(row[0])

    results.sort(
        key=lambda x: x["record_id"]
    )

    checkpoint = {
        "model": MODEL,
        "model_sha": info.sha,
        "task": info.pipeline_tag,
        "library": info.library_name,
        "records_expected": 401,
        "records_verified": len(results),
        "batch_size": BATCH_SIZE,
        "timeout_seconds": TIMEOUT_SECONDS,
        "results": results,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            checkpoint,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"  checkpoint: {len(results)}/401"
    )
    print()

cosines = np.array(
    [r["cosine"] for r in results],
    dtype=np.float64,
)

max_abs = np.array(
    [r["max_abs"] for r in results],
    dtype=np.float64,
)

mean_abs = np.array(
    [r["mean_abs"] for r in results],
    dtype=np.float64,
)

l2 = np.array(
    [r["l2"] for r in results],
    dtype=np.float64,
)

print()
print("========================================")
print("FULL GRANITE REPRODUCIBILITY AUDIT")
print("========================================")
print("Expected records      :", 401)
print("Verified records      :", len(results))
print("Model SHA             :", info.sha)
print(
    "Minimum cosine        :",
    f"{cosines.min():.12f}",
)
print(
    "Mean cosine           :",
    f"{cosines.mean():.12f}",
)
print(
    "Maximum cosine error  :",
    f"{1.0 - cosines.min():.12e}",
)
print(
    "Maximum absolute diff :",
    f"{max_abs.max():.12e}",
)
print(
    "Mean absolute diff    :",
    f"{mean_abs.mean():.12e}",
)
print(
    "Maximum L2 difference :",
    f"{l2.max():.12e}",
)

for threshold in (
    0.999999,
    0.99999,
    0.9999,
):
    count = int(
        np.sum(cosines >= threshold)
    )

    print(
        f"Cosine >= {threshold}: "
        f"{count}/401"
    )

final = {
    "model": MODEL,
    "model_sha": info.sha,
    "task": info.pipeline_tag,
    "library": info.library_name,
    "records_expected": 401,
    "records_verified": len(results),
    "all_records_verified": len(results) == 401,
    "min_cosine": float(cosines.min()),
    "mean_cosine": float(cosines.mean()),
    "max_cosine_error": float(
        1.0 - cosines.min()
    ),
    "max_absolute_difference": float(
        max_abs.max()
    ),
    "mean_absolute_difference": float(
        mean_abs.mean()
    ),
    "max_l2_difference": float(
        l2.max()
    ),
    "results": results,
}

OUTPUT.write_text(
    json.dumps(
        final,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

print()
print("Final report:", OUTPUT)
print("=== COMPLETE ===")
