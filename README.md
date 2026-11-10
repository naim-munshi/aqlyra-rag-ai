# Aqlyra AI

**In 30 seconds:** Full-stack, multilingual Knowledge RAG + general AI chat. Next.js/Vercel frontend, FastAPI/Render backend, Neon PostgreSQL + pgvector, Redis and a separate 384D semantic worker. Private Knowledge combines genuine dense and lexical retrieval, RRF fusion, evidence context and traceable citations.

**Verified result (10 November 2026):** **1,035 / 1,035 eligible ready chunks indexed** with matching current-model semantic vectors (`bekko-static-multilingual-int8-mrl384-v1`); **7 quarantined answer-key chunks excluded**. This measures **index coverage only**, not precision, grounded-answer accuracy, speedup or user-level E2E reliability.

**Real-model offline benchmark (10 November 2026):** IBM Granite 97M multilingual R2, 384D genuine model weights, **20 English synthetic queries over 30 generated chunks**, Hit Rate@1 **0.90**, Hit Rate@3 **1.00**, MRR@5 **0.933**. This is an **offline dense-only test**, not end-to-end production accuracy or a directly comparable rerun of the historical 70-chunk deterministic baseline. [Measured GitHub Actions run](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42760735012) · [Benchmark methodology PR #176](https://github.com/naim-munshi/aqlyra-rag-ai/pull/176).

**See it:** [Live application](https://aqlyra-ai.vercel.app) · [Public scripted demo](https://aqlyra-ai.vercel.app/demo) (*no live inference in demo*) · [Backend evaluation protocol](backend/evaluation/REPRODUCIBLE_PROTOCOL.md).

**Status:** Publicly accessible engineering beta/development deployment, **not enterprise-production certified**. Real Google/password session E2E, multilingual voice E2E, controlled semantic benchmark and backup/restore acceptance are independent outstanding gates. The protected `main` branch is a historical baseline, not the deployed backend.

---

## Detailed architecture, evidence and historical operational notes

**Source-grounded AI chat, private-document RAG, web research and an auditable full-stack deployment.**

[Current repository review](docs/REPOSITORY_CLEANUP_REVIEW_2026-11-08.md) · [Security assessment](docs/SECURITY_AUDIT_2026-11-08.md) · [Live application](https://aqlyra-ai.vercel.app) · [Demo and acceptance guide](docs/PRODUCT_DEMO_AND_ACCEPTANCE.md) · [GitHub Actions](https://github.com/naim-munshi/aqlyra-rag-ai/actions) · [Historical 31 October status](docs/PRODUCTION_STATUS_2026-10-31.md)

> **Operational review — 8 November 2026:** The deployed **backend** uses `release/core-without-study-abroad-20261027` (Render) and the official **frontend** uses `fix/center-empty-chat-composer-20261102` (Vercel). The protected `main` branch is **not** the deployed release; do not merge either divergent release or delete branches without checking full review gates. Automatic public Web Research/follow-ups and a bounded 429 fallback have shipped. Knowledge has tenant-scoped lexical fallback for documents without semantic vectors; real 384D embedding recovery increased coverage from **22 to 26 of 1,030 chunks** in the bounded November 8 test. This is **not** full dense RAG coverage. Browser-authenticated two-user acceptance, real LiveKit voice E2E, durable artifact storage, and encrypted off-host backup/restore remain outstanding. Render Free cold starts and provider quotas affect availability. Verify current deployment health and exact-head CI instead of assuming the historical table below is current. See [repo cleanup audit](docs/REPOSITORY_CLEANUP_REVIEW_2026-11-08.md) and [security assessment](docs/SECURITY_AUDIT_2026-11-08.md).

> **Production beta — verified 31 October 2026.** Aqlyra has a live Next.js frontend on Vercel, FastAPI backend on Render, Neon PostgreSQL/pgvector, Redis, cloud document storage, Groq-based chat, Tavily-backed Web Search, and a separate authenticated multilingual semantic-embedding worker. Some features remain limited or disabled; see the status matrix. Live availability and provider quotas can change after this verification date. A green CI build is not a replacement for authenticated user acceptance.

## What Aqlyra does

**Converse** provides multi-turn AI chat, user-scoped history and memory, web research when needed, and selected attachment/image handling. Web answers should show source references; general model responses are not automatically verified facts.

**Knowledge** is a private-document RAG workflow. Users upload supported files, the service parses and chunks text, retrieves relevant evidence using dense semantic vectors and lexical search, builds a bounded context, and validates document citations. Documents, conversations, attachments and memory have owner-scoped access controls.

**Web Search** currently uses **Tavily in production**. An independent, token-protected SearXNG gateway is under controlled acceptance; a real 5-result probe has succeeded using a bounded Wikimedia fallback, but that is not equivalent to a complete independent general-purpose web index. Tavily must not be disabled until broad search accuracy, source quality and outage behavior pass live acceptance.

> **2026-11-02 incident update:** The official frontend now exposes real-time LiveKit Voice only; user microphone E2E is BLOCKED by two missing Render LiveKit credential values. Semantic embedding reliability is degraded by repeat 502s. Groq returned intermittent 413/429 errors. Treat the 31 October acceptance baseline below as historical; see [verified recovery directive](docs/AQLYRA_MASTER_ENGINEERING_BASELINE.md).

## Historical capability matrix (31 October–2 November 2026)

| Capability | Historical verification | Important qualification |
| --- | --- | --- |
| Email and Google identity; authenticated chat | Production beta | Two-account browser/security E2E not yet certified |
| General Converse with Groq | Live; reliability work open | 2026-11-01 production logs include successful 200 responses and occasional 413 payload-too-large / 429 rate-limit errors; response quality and recovery need real-user validation |
| Memory recall | Degraded during semantic-worker outages | Repeated live embedding HTTP 502 caused documented lexical fallback; no claim of semantic recall reliability until real-provider acceptance |
| PDF Knowledge ingestion and lexical search | Verified | One legacy PDF was recovered into **12 chunks** |
| Dense semantic RAG | Earlier provider/database canary PASS; ongoing 502 incident | Preserved genuine **384-d** vectors and original multilingual ONNX model; a bounded transient retry/circuit breaker is in PR #93, not evidence that worker health is restored |
| Tavily Web Research | Provider pipeline verified | Real public canary returned four validated sources; citations do not guarantee factual truth |
| Self-hosted SearXNG | Limited canary PASS | Wikipedia-backed 5-result probe; wider web coverage/zero-result resilience not yet certified |
| Browser Voice | No longer offered as silent fallback on official frontend | Browser synthesis cannot reliably support hands-free interruption on iOS. Official Voice UI uses LiveKit-only connection and reports unavailability rather than simulating a call |
| LiveKit realtime voice | Worker registered; real call BLOCKED | Railway 1/1 replica Online, but Render startup diagnostics show missing **LIVEKIT_API_KEY** and **LIVEKIT_API_SECRET**. Authenticated room/audio, STT, TTS, barge-in and two-account E2E remain unverified |
| Browser Agent | **Disabled in production** | Signed approvals and Redis replay protection do **not** replace network-isolated browser execution |
| PDF/DOCX/XLSX/PPTX/other artifact generation | Implemented | Format-specific and cross-user production acceptance outstanding |
| Backups | Neon recovery branch exists | **Off-host encrypted export + isolated database/object restore remain unverified** |

For the auditable version of this table, run instructions and known limitations, see [Production Status](docs/PRODUCTION_STATUS_2026-10-31.md).

## Try Aqlyra

1. Open **[the live app](https://aqlyra-ai.vercel.app)** and sign in if needed. An explicitly linked [**/demo**](https://aqlyra-ai.vercel.app/demo) is a *scripted, non-inference portfolio walkthrough*; it is not proof of live RAG.
2. Under **Converse**, ask a standard multi-turn question, then a time-sensitive question with Web Search. Verify source URLs and distinguish page-backed content from uncertain assertions.
3. Under **Knowledge**, upload a non-sensitive test PDF, select it, then ask one answerable question and one unsupported question. Verify document citations and refusal behavior.
4. If LiveKit Voice is configured, test a real authenticated microphone session and confirm the agent connects. The official UI does not substitute browser speech as a fake live call; a microphone E2E PASS has not been established by the automated deployment checks.
5. Do not attempt production Browser Agent execution while its isolated sandbox is disabled.

**Full reproducible demo:** [PRODUCT_DEMO_AND_ACCEPTANCE.md](docs/PRODUCT_DEMO_AND_ACCEPTANCE.md) includes an interviewer-friendly five-minute flow, synthetic sample materials, safe test prompts and PASS/FAIL evidence requirements. Never upload actual passports, customer secrets or other sensitive records as demo data.

## Architecture

~~~mermaid
flowchart TB
  U[Browser] --> F[Next.js on Vercel]
  F --> API[FastAPI on Render]
  API --> GROQ[Groq LLM]
  API --> SEARCH[Tavily Web Research]
  API -. limited independent search .-> SX[Token-protected SearXNG / Wikimedia gateway]
  API --> DB[(Neon PostgreSQL + pgvector)]
  API --> REDIS[(Redis rate limits)]
  API --> OBJ[(Private cloud documents)]
  API --> EMB[Authenticated semantic worker]
  EMB --> ONNX[Compact multilingual ONNX vectors]
  OBJ --> PARSE[Parse, OCR, chunk]
  PARSE --> DB
  API --> HY[Dense + lexical retrieval / fusion]
  HY --> DB
  HY --> CIT[Evidence, answer and citation validation]
  API -. controlled, disabled .-> BROWSER[Browser Agent execution]
  F -. browser-dependent .-> SPEECH[Web Speech fallback]
~~~

The semantic worker is separate from the main API because a larger contextual E5 ONNX model exceeded a **512 MiB** free-service memory limit. The deployed compact *static* multilingual encoder was tested in its own 512 MiB container. It is a real pretrained semantic representation, but it is not equivalent to a large contextual sentence model. The vector schema is 384-dimensional, and lexical retrieval remains available as fallback.

## Repository map

| Path | Purpose |
| --- | --- |
| [frontend/](frontend/) | Next.js authenticated workspace, UI, proxy API, public scripted portfolio demo |
| [backend/app/api/](backend/app/api/) | FastAPI endpoints and ownership enforcement |
| [backend/app/services/](backend/app/services/) | Converse, web research, file/indexing, RAG, browser and artifact orchestration |
| [backend/app/embeddings/](backend/app/embeddings/) | Provider registry and isolated semantic-worker HTTPS client |
| [backend/semantic_worker/](backend/semantic_worker/) | CPU-only, token-protected pretrained multilingual semantic encoder |
| [backend/app/retrieval/](backend/app/retrieval/) | Dense + lexical retrieval and rank fusion |
| [backend/app/rag/](backend/app/rag/) | Context, citations and grounding checks |
| [ops/searxng/](https://github.com/naim-munshi/aqlyra-rag-ai/tree/feat/hybrid-searxng-web-research-20261031/ops/searxng) | Optional keyless metasearch gateway and bounded fallback |
| [.github/workflows/](.github/workflows/) | Python/PostgreSQL, Node/Next.js, security, dependency, Docker, ARM64 and model acceptance |
| [docs/](docs/) | Setup, architecture, production acceptance and handoff |

## Develop and test

Use separate local test credentials and a disposable database. **Never point a test or CI runner at the production Neon database.**

~~~bash
cp -n backend/.env.example backend/.env
docker compose --env-file backend/.env up -d --build postgres redis backend
cd frontend
npm ci
cp -n .env.example .env.local
npm run dev
~~~

Backend verification (from a configured developer environment):

~~~bash
cd backend
python -m pytest -q
~~~

Frontend verification:

~~~bash
cd frontend
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
~~~

The production stack requires real provider/environment configuration; development defaults and mocked tests are *not* evidence of production answer accuracy. See [SETUP.md](docs/SETUP.md), [Architecture](docs/ARCHITECTURE.md) and [Security](docs/SECURITY_TESTING.md). For voice and Browser Agent safety, review [the production status matrix](docs/PRODUCTION_STATUS_2026-10-31.md) before enabling any flags.

## Production safety and release process

- Current backend release: **`release/core-without-study-abroad-20261027`**. Frontend Vercel release: **`release/unified-core-frontend-rag-20261031`**; they are separate release tracks.
- Keep protected `main` unchanged unless the repository owner explicitly approves a reviewed merge.
- Use exact-head GitHub CI, limited-scope PRs, non-destructive deployment, post-deploy HTTP checks and sanitized logs.
- Never log API tokens, original user messages, private uploaded content or browser approval secrets.
- Browser Agent production execution must remain disabled until separate network/OS isolation, outbound host controls, durable approvals and real E2E are proven.
- A Neon recovery branch protects a point-in-time database state, but **does not constitute an encrypted off-host backup or verified restore**.
- Do not claim SMTP, voice, document permissions or cross-account production acceptance without actual end-to-end evidence.

See [RELEASE_ACCEPTANCE.md](docs/RELEASE_ACCEPTANCE.md) and [PRODUCTION_STATUS_2026-10-31.md](docs/PRODUCTION_STATUS_2026-10-31.md) for release gates.

## License

See [LICENSE](LICENSE).
