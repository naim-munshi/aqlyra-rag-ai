# Aqlyra FastAPI backend

The production API for the Aqlyra AI platform. Source is released separately from the frontend Vercel branch and optional SearXNG gateway.

**Production beta:** https://aqlyra-api-free-launch.onrender.com · [Main README](../README.md) · [Status matrix](../docs/PRODUCTION_STATUS_2026-10-31.md)

## Runtime services

- **Converse:** auth, chat history, selected attachment/image handling, memory and user-scoped context.
- **Knowledge:** PDF/Office parsing, bounded chunk indexing, lexical+semantic RAG, source validation and refusal for unsupported questions.
- **Web:** Tavily is the active broad public search; SearXNG is a separately gated, limited independent candidate.
- **Embedding:** `remote_onnx` sends bounded texts over authenticated HTTPS to the separate Render semantic worker; returned normalized pretrained dense vectors have 384 dimensions. It is not the deprecated Hugging Face inference-credit dependency.
- **Identity:** verified account flows, OAuth ID token verification, JWT sessions and tenant ownership checks.
- **Browser/voice:** LiveKit worker infrastructure is optional; production Browser Agent execution remains disabled pending sandbox acceptance.
- **Persistence:** Neon PostgreSQL/pgvector, private cloud objects and Redis rate limiting.

No production credentials should be logged or stored in Git.

## Local development

Use a **disposable** PostgreSQL test instance, not production Neon:

~~~bash
cp -n .env.example .env
# From repository root: docker compose --env-file backend/.env up -d --build postgres redis backend
cd backend
python -m pytest -q
~~~

AI providers require separate opt-in configuration. Tests may use deterministic fixtures; those are not evidence of live model accuracy.

## Operational checks

- `GET /api/v1/health`: process is running.
- `GET /api/v1/readiness`: dependency checks; no raw secrets.
- `GET /api/v1/metrics`: operational metrics per security configuration.

Current full-scope source candidate: `release/study-abroad-included-20261129` (Study Abroad included). It is based on the historical `release/core-without-study-abroad-20261027` release line; that legacy name does not mean Study Abroad is excluded from the candidate code. This branch is not proof of a Render deployment. Verify the exact Render deployed SHA and run Study Abroad/auth/RAG staging E2E before claiming backend parity. Never merge to protected `main` without independent review and owner approval. Browser Agent remains disabled by default; the keyless search backend must not replace Tavily until broad, cited live tests pass.

See [full acceptance](../docs/RELEASE_ACCEPTANCE.md), [demo script](../docs/PRODUCT_DEMO_AND_ACCEPTANCE.md) and [recorded status](../docs/PRODUCTION_STATUS_2026-10-31.md).
