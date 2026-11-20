# Aqlyra frontend

The **actual production-beta Next.js application** for the Aqlyra AI platform. The former scripted public portfolio walkthrough is retired.

- **Real software:** https://aqlyra-ai.vercel.app (authenticated Converse, Knowledge, Web Research and supported voice fallback)
- **Retired preview:** `/demo` redirects to `/login`; scripted sample assets remain in the repository but are not exposed by the application.
- **Backend:** FastAPI on Render; sessions, data ownership, database and AI providers remain on the server side
- **Git deployment branch:** `release/unified-core-frontend-rag-20261031` (not the Core backend branch). Always compare its HEAD with the deployed Vercel commit before claiming a change is live.

## Features and limits

| Surface | Runtime behavior |
| --- | --- |
| Converse | Server-proxied authenticated AI messages, history, selected attachments, memory |
| Knowledge | Selected private documents, semantic/lexical retrieval, source citation display |
| Web | Tavily production provider; own keyless SearXNG is a limited independent canary |
| Voice | LiveKit when a real agent is configured; optional browser STT/TTS fallback depends on browser permissions and vendor support |
| Browser Agent | Safety-gated and **disabled** in production pending isolated sandbox |
| `/demo` | Disabled; redirects to the real sign-in page |

## Local setup

Node.js 24 and npm are recommended. Use a separate local backend and disposable test database.

~~~bash
cd frontend
npm ci
cp -n .env.example .env.local
npm run dev
~~~

Configure `BACKEND_API_URL` as a server-only local FastAPI address and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` as the public Google Web Client ID if used. Never put API keys, backend JWTs, database URLs or service credentials in `NEXT_PUBLIC_*` values. Real production routes use Next.js server-side proxy handlers with HttpOnly session cookies.

## Verification

~~~bash
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
~~~

Verify that an anonymous request to `/demo` redirects to `/login`, that the public landing page contains no demo links, and that `/login` still works with the configured backend. Cross-browser tests, actual authenticated voice and two-user file isolation require explicit manual acceptance; CI does not replace them.

## Production deployment

The real frontend is a Vercel Next.js project called `aqlyra`. It is not the separate `aqlyrax` project and not the backend Render service. Release only reviewed commits into `release/unified-core-frontend-rag-20261031`, verify exact-head CI and inspect the deployed commit/alias before saying the new UI is live.

The legacy `NEXT_PUBLIC_AQLYRA_DEMO_ONLY` variable is ignored by the active application. Anonymous visitors see the product landing page; the old `/demo` path redirects to `/login`.

See [Production status](https://github.com/naim-munshi/aqlyra-rag-ai/blob/release/core-without-study-abroad-20261027/docs/PRODUCTION_STATUS_2026-10-31.md), [Demo and acceptance](https://github.com/naim-munshi/aqlyra-rag-ai/blob/release/core-without-study-abroad-20261027/docs/PRODUCT_DEMO_AND_ACCEPTANCE.md) and [Release acceptance](../docs/RELEASE_ACCEPTANCE.md).
