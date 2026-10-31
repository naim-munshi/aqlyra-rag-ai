# Aqlyra isolated multilingual semantic worker

This is a **separate Render service**, not a process inside the main FastAPI container. It runs a compact pretrained multilingual *static* embedding model offline after build-time download, supplies normalized **384-dimensional** vectors and requires a high-entropy bearer token at `POST /v1/embed`. Do not expose that token in browser code or commit it to GitHub.

- A public health endpoint checks process readiness; health alone does **not** verify retrieval quality.
- The authenticated embedding route accepts bounded inputs and returns an explicit model name/dimension.
- This worker does **not** access Neon, cloud files or user accounts.
- A real 512-MiB container inference and authenticated HTTP test has passed, but capacity/latency must be monitored under production traffic.
- Main backend supports lexical fallback when the embedding service is unavailable.
- Existing document vectors can be reindexed through a bounded **operator-only** backfill, default off after use.

Do not claim that the static encoder is equivalent to the larger contextual E5 model: the latter exceeded the 512-MiB memory budget during acceptance.

## Tests

See [`.github/workflows/isolated-semantic-worker.yml`](../../.github/workflows/isolated-semantic-worker.yml) and the main backend test suite. The worker's model download must never be triggered by unauthenticated user input.

## Operating notes

Deploy from the reviewed Core release branch using Render's `backend/semantic_worker/Dockerfile`; use an independently generated `SEMANTIC_WORKER_TOKEN` secret. The API's `REMOTE_SEMANTIC_URL` and `REMOTE_SEMANTIC_TOKEN` are server-only. Run a real vector count and retrieval relevance test after changing models, because vectors from different models must not be silently mixed.

[Production status](../../docs/PRODUCTION_STATUS_2026-10-31.md) · [System architecture](../../docs/ARCHITECTURE.md)
