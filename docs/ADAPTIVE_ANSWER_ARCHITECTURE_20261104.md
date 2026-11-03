# Aqlyra Adaptive Answer Architecture — Production Plan

Scope: improve the existing Next.js/FastAPI/Groq/Tavily/SearXNG/PostgreSQL/LiveKit stack without rebuilding it.

## Observed incident

Production logs on 2026-11-04 JST showed multiple Groq HTTP 429 responses, paid model retries and second-pass citation repairs on short public fact questions. A 200 SSE handshake in milliseconds does not measure time to final answer. Semantic-memory embedding also hit 429, falling back to lexical.

## Answer lanes

1. Direct conversation: evergreen information, greetings, writing and ordinary reasoning use a streamed LLM response without web or embeddings unless required.
2. Exact tools: safe bounded arithmetic and other deterministic operations run directly; no model guessing.
3. Fast verified fact: identify a public current-officeholder query, choose a first-party government publication, extract the live page, verify explicit role/name labels, and return a one-sentence sourced answer without Groq when validation succeeds. If primary evidence fails validation, abstain or use bounded sourced synthesis, never guess.
4. Current general web: for public news, market figures and current rules, search 2–5 relevant documents then generate one grounded answer with citations.
5. Private document RAG: strict account and future company-tenant authorization precedes hybrid retrieval, reranking and generation. Never send private context to public search.
6. Deep research: only explicitly longer or multi-step questions use several searches, heavier reasoning and more sources.
7. Voice: reuse the same answer brain with a strict latency target and distinct voice turn-taking/UI safety.

## Latency and reliability

- A simple one-name officeholder question should target one public search and one official extraction; one or two sources are enough.
- Do not apply last-month publication filters to evergreen official administration pages.
- Limit requests, model retry loops and duplicate citation repairs. Groq 429 means provider capacity is exhausted, not that further waiting automatically improves answer quality.
- A server-owned official source URL can be pinned but its live content must still be extracted and validated; never hardcode a human name.
- Only list sources actually cited in the answer; show the result in one short sentence for short questions.
- Record privacy-preserving end-to-end stage timings and rate-limit counts, not prompt text or credentials.
- Keep document permissions enforced server-side regardless of claims like 'I am the CEO'.

## Acceptance

- Backend PostgreSQL 16+18 full suite with synthetic public-fact/typo, missing source, hallucination and privacy regression tests.
- Staging end-to-end real-provider p50/p95 latency and citation accuracy; never treat mock throughput as production inference throughput.
- Live authenticated tests for Bangla shorthand about PM, US president, private RAG, Web Off, normal chat and longer research.
- Separate scalability/voice/device/enterprise RBAC gates before claiming enterprise readiness.

The fast lane covers only narrowly verified primary-source facts; a universal 100% correct answer guarantee is not possible.