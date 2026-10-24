# Real web research in Aqlyra

The authenticated **Web Research** link in the main sidebar opens `/web`.
This is distinct from document-only Knowledge mode, and web citations use
`[W1]`, `[W2]` rather than private-document `[S1]` markers.

## Configuration

No new database schema is needed for browsing.

Configure privately in `backend/.env`:

```dotenv
WEB_RESEARCH_ENABLED=true
TAVILY_API_KEY=tvly-REPLACE_WITH_YOUR_OWN_KEY
LLM_PROVIDER=groq
GROQ_API_KEY=REPLACE_WITH_YOUR_OWN_KEY
LLM_MODEL=openai/gpt-oss-20b
```

Or use an existing configured OpenAI provider. The feature refuses to pretend
that deterministic test models are real AI. Obtain a Tavily search API key at
https://app.tavily.com and check your provider's free credit allowance.

When running FastAPI natively, restart the backend after configuring the
env file. The frontend reads no provider key: it talks to the same-origin
`POST /api/web/research` Next.js proxy, which forwards the existing HttpOnly
session token server-side to the backend.

## Execution and security

1. Authenticate the user, validate bounded question (3–600 chars).
2. Search live via HTTPS Tavily API. Filter response URLs to public HTTPS
   hosts; reject IP literal, nonstandard port and local/internal hosts.
3. Ask Tavily to extract relevant public webpage content, without direct
   arbitrary URL fetches from the Aqlyra backend.
4. Bound each web excerpt to 3,000 chars and send to the configured LLM as
   untrusted evidence.
5. Reject model answers without valid `[W#]` references; present actual
   extracted source links separately in the UI.

Aqlyra does not execute instructions found in webpages, run browser scripts,
click arbitrary links, submit website forms or browse private/authenticated
sites. This is a source-reading web research agent, not autonomous
computer use. No browser history is persisted as conversation messages.
Web research can incur Tavily and model API usage charges depending on plans.
The existing RAG endpoint rate limiter is applied when configured with Redis;
for public service deployments, configure and verify ingress abuse protection.
