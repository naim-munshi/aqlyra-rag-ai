# Automatic Web Research in Aqlyra Converse — isolated release candidate

## Scope

This branch extends the EXISTING Full release candidate (#37), not `main`.
It does not replace Knowledge RAG, pgvector, private documents, voice, Study
Abroad, auth, guest access, document persistence, migrations, or the standalone
`/web` and `/agent/browser` workspaces. Do not merge or deploy without
the release owner's approval and exact-head CI and end-to-end gates.

Normal authenticated chat has four user-selectable modes:
- **Web: Auto** (default): deterministically detects explicit public web
  research requests and date-sensitive questions in English, Bangla, Japanese.
  If `WEB_RESEARCH_ENABLED=false`, falls back to ordinary normal chat
  without asserting a web lookup. Auto does NOT make requests for ordinary
  timeless/private-file questions.
- **Web: On**: forces live source-backed public web research; when unconfigured,
  returns a transparent error rather than an ungrounded LLM answer.
- **Deep web**: user-triggered two bounded Tavily Search calls (the original
  query and a primary-source evidence variant) with advanced extraction,
  cross-host diversification, and at most five source citations. This is a
  two-query research workflow, **not** an unbounded autonomous agent.
- **Web: Off**: never searches public web.

The mode travels from the chat composer through the existing authenticated
Next.js stream proxy to `ConversationMessageCreate.web_mode`, then the
existing normal-chat backend. Old clients default to Auto. Existing streaming
SSE `start/delta/complete/error` and conversation persistence are reused.

## Security and privacy

- Only the current user question is sent to Tavily and the configured LLM.
  No private history, memory, retrieval chunks, API credentials or file
  contents enter the research provider. The Knowledge-mode and attachment
  paths take priority; the web selector cannot override them.
- Reuse fixed Tavily endpoints, public HTTPS URL checks, included-domain
  filtering, bounded extraction, source citation verification, prompt
  injection isolation, existing account auth and rate limiting.
- The response includes clickable, sanitized source links in conversation
  Markdown and can be restored from history. Web [W#] source references
  are never misrepresented as private Knowledge [S#] citations.
- Never silently fall back from failed web research to a guessed general
  model answer. Real Tavily, embeddings, LLM and costs remain dependent on
  existing private configuration.
- Classification is deliberately deterministic, not a claim of fully
  intelligent tool planning. The user can select On/Off/Deep to override.

## Acceptance and rollout

1. Pass exact-HEAD backend PostgreSQL tests and frontend lint/typecheck/build,
   dependency audits, network boundary regression and source-citation tests.
2. In isolated HTTPS staging, configure a privately stored
   `WEB_RESEARCH_ENABLED=true`, `TAVILY_API_KEY` and a real approved LLM.
   Never use the development-only keyless mode in production.
3. With a real signed-in test account, verify Auto timely search, Off no
   Tavily egress, On mandatory citations, Deep two bounded search passes,
   citations still available after a browser refresh, and mobile selector.
4. Simulate Tavily timeout/429, malicious HTML/link/source title, invalid
   provider [W99], misconfigured model, secret-looking prompts, unsupported
   document attachments and account isolation. Errors must be transparent
   and no failed answer should be committed to history.
5. Validate provider cost/rate limits, monitoring and abuse resistance before
   considering public enablement. No auth, guest or Vercel security bypass.

Current implementation evidence is source + regression tests only; real
live provider and production rollout remain NOT VERIFIED.
