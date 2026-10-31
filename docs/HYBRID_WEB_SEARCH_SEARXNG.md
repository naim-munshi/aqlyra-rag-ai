# Aqlyra Hybrid Web Research — SearXNG-first

## Architecture

Aqlyra keeps the existing Converse + /api/v1/web/research routes, Auto/On/
Deep/Off controls and [W#] citations. Only the search/evidence providers
change. Private RAG, documents, chat history, personal memories, authenticated
accounts and admin traffic are never sent to SearXNG or Tavily.

- `WEB_SEARCH_PROVIDER=auto`: keyless **SearXNG first**, then Tavily
  **only if configured**, with bounded failure fallbacks.
- `WEB_SEARCH_PROVIDER=searxng`: keyless SearXNG only (no Tavily).
- `WEB_SEARCH_PROVIDER=tavily`: previous Tavily route only.
- `SEARXNG_BASE_URL`: operator-set HTTPS endpoint; users cannot choose it.
- `SEARXNG_SERVICE_TOKEN`: optional private gateway shared-secret header;
  never sent to search result websites or user browser.
- `SEARXNG_READ_PAGES_ENABLED`: default false. When true, HTTPS page reader
  resolves public IPv4, **pins that IP**, verifies TLS hostname, blocks
  redirects, private/reserved IPs, unapproved MIME types, decompression,
  large bodies, and JavaScript execution; 3,000 chars max per source.
- Without readable full pages, Search result excerpts are explicitly marked
  **incomplete evidence**. Current officeholders or changing policies must
  not be asserted using snippets alone.
- Original Q/A citation validation remains strict: only approved [W#]
  identifiers and approved source URLs.

## Local Docker Compose (API key not needed)

Set a strong `SEARXNG_SECRET` locally in your private .env file and run:

```sh
docker compose --profile web-search up -d searxng
```

`ops/searxng/settings.yml` explicitly enables SearXNG JSON output, because
SearXNG defaults to HTML-only JSON=403 unless formats are configured.
The SearXNG container has **no host-published port**. Backend and search
must share the Compose network. In the backend development environment:

```dotenv
WEB_RESEARCH_ENABLED=true
WEB_SEARCH_PROVIDER=searxng
SEARXNG_BASE_URL=http://searxng:8080
SEARXNG_READ_PAGES_ENABLED=false
```

The HTTP Compose URL is only accepted by the backend when
`APP_ENV != production` and hostname exactly `searxng`, port 8080.
Production permits only a trusted HTTPS hostname (not localhost or IP).

## Render production

Never deploy an unauthenticated public SearXNG endpoint and put it
directly into `SEARXNG_BASE_URL`: open search endpoints attract scraping
and can trigger search-engine CAPTCHA, outbound traffic abuse, or Render
suspension. A paid **private Render service in the same region**, or a
protected HTTPS gateway that verifies `SEARXNG_SERVICE_TOKEN` before
proxying only bounded `GET /search?format=json`, is required.

Create and test this infrastructure separately, then set
`SEARXNG_BASE_URL` and optional `SEARXNG_SERVICE_TOKEN` as secret/private
Render variables on the existing `aqlyra-api-free-launch`. No frontend
rebuild, main merge, or database migration should be needed.

Before enabling production:
1. Real SearXNG JSON probe through the backend's network, 2xx and >=1
   public source. Verify no private URL, unknown MIME or redirects.
2. Web Auto/On/Deep/Off E2E with authenticated user, recent official
   Bangladesh/Japan leadership, EN/BN/JA, mobile Safari and citations.
3. Multi-user isolation; rate limits; CAPTCHA, outage, 429, latency and
   search-engine refusal behavior.
4. Source-backed answer versus insufficient evidence, and non-secret health
   `searxng_configured_unverified` status **does not** mean a live probe PASS.
5. Check provider egress budget, rollback, logs, legal/robots/terms, and
   privacy retention. Do not turn on automated broad crawling or unrestricted
   Browser Agent.

### Acceptance and release

- Exact SHA GitHub CI full backend/PostgreSQL 16+18, security, frontend,
  Docker/ARM64 tests PASS.
- Use a reviewed Draft PR stacked onto current Core release branch;
  no protected `main` merge without explicit approval.
- Provider URL and live credentials are external release gates. Do not
  manufacture a public instance URL, claim full live success from CI or
  silently enable feature flags.

## Real availability limitations (October 31, 2026)

SearXNG's public upstream engines may rate-limit cloud hosting addresses and return zero results. The protected gateway now offers an explicitly bounded **Wikipedia MediaWiki API** fallback for a zero-result SearXNG response. It only returns real, live public search hits with valid positive page IDs, canonical Wikipedia URLs and sanitized snippets. It is not a private crawler, broad independent web index or real-time news search. When no real source exists, it must not synthesize sources or claim successful independent search. The gateway's startup probe checks the full authenticated search path. Keep production `WEB_SEARCH_PROVIDER=tavily` until real result counts, response latency, citation validity, and fallback behavior all pass an operator-approved release gate.

The fallback also attempts the documented Wikipedia REST page-search API if the MediaWiki Action API has no usable results. Both use fixed HTTPS hostnames and only verified API response page URLs. Current cloud egress probes can still return zero; always keep Tavily selected until a live acceptance gate passes.
