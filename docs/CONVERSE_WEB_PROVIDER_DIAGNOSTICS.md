# Converse Web Research provider: safe production diagnostics

The actual production screenshot showed correct *fail-closed* public-office
handling (no more invented politicians) but **no live Web Search answers**.
Converse's Auto mode uses Tavily through `WEB_RESEARCH_ENABLED` and
`TAVILY_API_KEY`; Groq is the *answer LLM*, not a live search engine.

This hotfix exposes no credentials and changes no web-search routing,
permissions, user data, database schema or provider billing configuration.

Readiness reports one of:
- `disabled_and_missing_key`: neither flag nor Tavily credential configured.
- `disabled_key_present`: Tavily credential present but feature flag OFF.
- `missing_tavily_api_key`: Web enabled, credential absent.
- `configured_unverified`: flag and credential appear present; **NOT
  proof of successful live search, quota, evidence extraction or citations**.

The same status is logged *once at FastAPI startup* without key values, and
Converse's public-fact fallback explains whether an administrator needs to
connect/enable Tavily, rather than implying users can repair server settings
by pressing the Chat Web Search selector.

## Follow-up production gate
1. Verify source commit, 7/7 GitHub CI, current Render live and rollback.
2. Deploy this diagnostic-only commit without changes to env, database,
   credentials or private files.
3. Confirm non-secret startup status in Render logs.
4. If credential **present but flag OFF**, activate only after checking
   credits/rate limits and running a real authenticated source-backed probe.
5. If key **missing**, obtain an approved Tavily key in the vendor's account;
   store it only in Render's secret configuration, **never** GitHub, screenshots,
   project files or chat messages. Merge update; do not replace other envs.
6. Validate source-grounded answer for public Bangladesh/Japan leadership,
   citations, multilingual & mobile streaming, Web Off/On/Auto, quota/429,
   and no private-document/history egress. Only then mark real Web PASS.

Without a production Tavily credential, there is no honest code-only
fix that supplies general live search. Do not hardcode current leaders,
fabricate citations, or turn on unverified proxy scraping in production.
