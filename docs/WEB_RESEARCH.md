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

For local-only testing, Tavily's official SDK also supports keyless Search
and Extract requests: set \`TAVILY_KEYLESS_ENABLED=true\` and leave
\`TAVILY_API_KEY\` empty. This is opt-in and disabled for production, and
may be rate-limited or unavailable; use a real API key for reliable service.

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

## Existing native Mac environment

Once the branch is checked out and the isolated PostgreSQL database is
online (port 55416), configure a real Groq/OpenAI model in `backend/.env`
and use `bash scripts/ops/native_web_research_up.sh`. This checks the
database schema, preserves existing uploads, starts only a verified
Aqlyra process bound to port 8010, and opens the authenticated `/web`
workspace on the already-running Next.js frontend. It does **not**
start Docker, reset or migrate databases, or touch Metriqen processes.
If no Tavily key is present, this helper explicitly enables Tavily's
local keyless Search/Extract mode; provider limits may apply.

## Mobile-first research workspace

The same authenticated `/web` page now has a responsive bottom composer:
- Open the **+** research tools sheet with accessible keyboard Escape support.
- Select **Search**, **Deep Research**, **Compare**, **Fact-check**, or
  **Read a public URL**. These are real backend research modes, not
  decorative buttons or fake progress animations.
- Deep mode explicitly uses Tavily advanced search and extraction, which
  may spend more API credits than basic mode.
- URL mode uses Tavily Extract only; it will **not** fetch a URL directly
  from the Aqlyra server. Only public HTTPS URLs are allowed.
- The **Document workspace** link returns to the original private-file
  environment; public web research never implicitly uploads local documents.
- Research history is **in-memory for the current tab only**; it is not
  stored in the database or in localStorage. **Clear** discards it.
- **Copy** writes the result to the clipboard; **Save** exports a local
  Markdown file with original source links. Neither is a cloud save.
- Enter submits a query; Shift+Enter enters a newline in the composer.

## Security and testing

Use `POST /api/v1/web/research` with
`{"question":"...","mode":"search","max_sources":4}`. Other mode values:
`deep`, `compare`, `fact_check`, `url`. The `url` mode requires
`source_url`, validated as public HTTPS before Tavily Extract is called.
No other modes accept `source_url`.

All API modes require the existing authenticated Aqlyra session.
The first-party Next.js route validates the shape; the FastAPI schema
enforces the same contract. Provider credentials never go to the browser.
The API surfaces errors instead of fabricating answers when search,
extraction, or cited synthesis fails.

Frontend validation tests: `cd frontend && node --experimental-strip-types
--test tests/*.test.mjs`. Backend tests include advanced mode and public URL
source extraction with mocked provider requests. CI uses no real Tavily
credits; manual testing with a real Groq/OpenAI model is still required.

## Research control upgrades

Search, Deep Research, Compare and Fact-check support an optional
`time_range` of `day`, `week`, `month` or `year`, plus at most three
`include_domains` hostnames (e.g. `arxiv.org`, `docs.python.org`).
The Next.js proxy and FastAPI schema both validate controls. Domain scoping
is enforced **again server-side on returned candidate URLs** so an
out-of-scope result cannot be extracted or cited even if provider filtering
is imperfect. Subdomains of selected sites are allowed; lookalike suffixes
are not. URL-only extraction never accepts search filters.

In Deep and Compare modes, the backend prefers independent hostnames when
selecting up to five sources, instead of accidentally returning five pages
from the same website. It does **not** guarantee that sources are independent
or that each claim is true. Freshness filters are provider search hints;
always inspect source publication dates rather than assuming all pages
were published recently.

These capabilities reuse the existing Tavily Search and Extract API. No
additional credentials or migrations are needed. Enabling Deep Research
still incurs the provider's advanced search/extraction credits.
