# Aqlyra production beta — verified state, 31 October 2026

This is a **time-bounded engineering evidence record**, not a lifetime uptime guarantee or a declaration that every feature has been accepted. Public URLs:

- App: https://aqlyra-ai.vercel.app
- Vercel project: `aqlyra`, **not** the separate `aqlyrax` project
- Backend: https://aqlyra-api-free-launch.onrender.com
- Semantic worker: https://aqlyra-semantic-worker.onrender.com (protected `/v1/embed`, no anonymous embeddings)
- Keyless search candidate: https://aqlyra-searxng-secure.onrender.com (token-protected search, public health only)
- GitHub: https://github.com/naim-munshi/aqlyra-rag-ai

## Verified evidence

| System | Evidence | Status | Limits |
| --- | --- | --- | --- |
| Frontend | Production Vercel deployment reported READY; Git production branch `release/unified-core-frontend-rag-20261031` | LIVE | Not all new frontend commits necessarily live; inspect deployment SHA |
| General AI | Core FastAPI on Render; Groq generation; startup and HTTP 200 | LIVE | No unconditional factual correctness guarantee |
| Public Web Research | Real Tavily search and Groq provider pipeline canary, 4 validated source references | PASS | Does not prove individual historical or current-officeholder answers |
| SearXNG | New token-protected gateway canary, 5 actual Wikimedia fallback results | LIMITED PASS | Wikimedia is narrow; no complete independent web/news coverage |
| Knowledge files | One private cloud PDF recovered: `ready`, 12 parsed chunks | PASS | User-specific, no cross-user production acceptance yet |
| Dense semantic model | Separate worker, real 384-d vectors, English/Japanese semantic smoke, 512-MiB container acceptance | PASS | Compact *static* model, not contextual E5; quality needs further evaluation |
| Database embeddings | 12 unique 384-d `remote_onnx` vector records for the existing document | PASS | New user uploads and end-to-end cited answers still require live scenarios |
| Memory | Quota-resilient user-scoped lexical fallback and CI tenant boundary tests | CODE/CI PASS | Real longitudinal conversational memory accuracy unverified |
| Browser Speech | Browser fallback code exists; may use browser-vendor speech recognition | CODE/CI | Microphone, Safari/iOS, device and production UI E2E unverified |
| LiveKit | Session/agent code exists | BLOCKED | Actual agent worker, provider STT/TTS and an RTC call not accepted |
| Browser Agent | Signed approvals + one-time Redis replay guard | HARDENED, DISABLED | No isolated execution/network egress policy, so **do not enable** |
| Backup | Point-in-time Neon recovery branch created | PARTIAL | Off-host encrypted DB + object backup and independent restore not verified |

## Deployment, provider and safety boundaries

Production API currently runs a reviewed backend Core release branch, and Vercel uses a **different frontend branch**. Updates to one do not automatically propagate to the other. Before reporting a feature as live, compare GitHub branch HEAD with Render deployment commit or Vercel deployment metadata, then validate HTTP health and an authenticated feature journey. CI can be green while the live frontend remains on a previous commit.

The keyless search service's Wikipedia-based fallback retrieves actual public entries from fixed HTTPS Wikimedia endpoints and never manufactures search results. A Wikimedia canary PASS must not be interpreted as a general internet crawler or sufficient justification to disable Tavily.

`remote_onnx` uses token-authenticated requests to the isolated worker. The worker loads a pretrained compact multilingual static model, returning 384-dimensional normalized vectors. Original uploaded files remain in private object storage; lexical retrieval remains a degraded-mode path if the worker fails.

Any demo outside the authenticated workspace must say **scripted sample** and must not suggest it uploaded a document or called live models. Do not expose private documents, user transcripts, environment variables, tokens, database URLs or session cookies in screenshots.

## Open acceptance gates (not PASS)

1. Browser and mobile authentication with two independent real test accounts, owner A/B file isolation and session revocation.
2. Live browser voice on Safari/Chrome; LiveKit RTC worker join/audio/STT/TTS requires an independently operating agent.
3. Browser Agent in a distinct sandbox with an egress allowlist, process caps, prompt-injection/SSRF hardening, durable single-use approvals and audited screenshots; currently **disabled**.
4. Independent broad-spectrum search quality tests (time-sensitive news, Japanese/Bangla queries, multi-domain search, extraction failures and citation validity) before replacing Tavily with SearXNG.
5. Off-host encrypted backup of DB and objects; isolated restore with documented RPO/RTO, retention and object checksum reconciliation.
6. Voice/privacy notices, mobile interaction and cross-device behavior.
7. Real Knowledge upload → indexing → semantic retrieval → validated citations and unsupported-question refusal for two different accounts.
8. Operations: alerts, p95 latency, resource utilization, rollback rehearsal and provider-budget monitoring.

**No approval for merging into protected `main` is implied by this document.**

## Reference docs

- [Live vs scripted demo](PRODUCT_DEMO_AND_ACCEPTANCE.md)
- [Architecture](ARCHITECTURE.md)
- [Release gates](RELEASE_ACCEPTANCE.md)
- [Keyless search candidate (PR #62)](https://github.com/naim-munshi/aqlyra-rag-ai/pull/62)
- [Browser Agent](BROWSER_AGENT.md)
- [Voice worker](../backend/app/voice/worker.py)
