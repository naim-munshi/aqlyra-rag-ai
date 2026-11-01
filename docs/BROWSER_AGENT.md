# Aqlyra Browser Agent v0.1 — approval-gated read-only browser

PR `feat/approval-gated-browser-agent` builds on the Office/Web Research
feature branches. The existing Web Research agent uses search/extract APIs.
This optional browser runtime actually opens public pages in a **fresh
headless Playwright Chromium context**, reads them and autonomously selects
same-host links using the configured real Groq/OpenAI LLM. It then gives
a page-by-page evidence trail and `[B1]` citations.

## Explicit safety scope

- **Plan -> Review -> Approve -> Execute**. The plan contains a short-lived
  signed token bound to the authenticated user's ID, task and approved host.
  Approval is a separate user click, never automatically issued by the AI.
- Disabled by default. Production is restricted to the **public HTML-only**
  DNS-pinned HTTPS reader when the operator explicitly enables it along with
  Redis-backed single-use approvals. It cannot use production Chromium,
  browser login, JavaScript, cookie sessions or desktop access.
- Public HTTPS only; the admin configures an exact hostname allowlist.
  DNS addresses must resolve globally. Request routing blocks all non-GET
  requests, scripts, downloads, service workers, cross-host requests and
  non-document resources. No persisted cookies or account credentials.
- The model may only choose the number of an eligible same-host link or
  finish. It cannot provide arbitrary JavaScript, selectors or OS commands.
- Maximum **four pages / 55 seconds**, bounded text excerpts, citations
  validated against visited pages. Content may contain prompt injections;
  it is strictly untrusted evidence.
- Read-only GET requests can still cause side effects on poorly designed
  websites. Only allow vetted public documentation/news sites. HTTPS/DNS
  validation is not a substitute for network namespace/egress isolation.
- Each approval lasts at most 120 seconds. Production uses Redis NX for
  distributed single-use redemption; a local in-memory ledger is only
  permitted in development. A missing Redis store fails closed. The local runner
  allows one active browser task at a time, with bounded wait and duration.

**NOT included:** local macOS mouse/keyboard control, Windows desktop access,
browser login/cookies, Javascript-rich sites, typing in forms, email sending,
site account changes, file deletion, payment or purchases. Do not advertise
those as implemented.

## Local Mac opt-in setup

From the existing checkout on this branch (no Docker required):

```bash
cd ~/aqlyra-rag-ai/backend
.venv/bin/python -m pip install -r requirements-browser-agent.txt
.venv/bin/python -m playwright install chromium
```

Chromium downloads a substantial browser binary. Confirm sufficient free
storage before installing (avoid resetting Docker volumes).

Set **privately** in `backend/.env` and restart the native FastAPI backend:

```dotenv
BROWSER_AGENT_ENABLED=true
BROWSER_AGENT_ALLOWED_HOSTS=docs.python.org,playwright.dev
LLM_PROVIDER=groq
GROQ_API_KEY=YOUR_PRIVATE_KEY
LLM_MODEL=openai/gpt-oss-20b
```

Use only vetted exact public hosts; no wildcards or arbitrary websites.
Then open `http://127.0.0.1:3000/agent/browser` and sign in, enter a task
and a public HTTPS URL matching the configured host, review the plan, then
click **Approve and run**.

## API

- `POST /api/v1/agent/browser/plan` — accepts `task`, `start_url`,
  returns signed 120s plan and exact capability restrictions.
- `POST /api/v1/agent/browser/execute` — requires `approved: true`
  and `plan_token`, returns cited report and visited-page audit trail.
- Next.js same-origin authenticated proxies:
  `/api/agent/browser/plan`, `/api/agent/browser/execute`.
  JWT session stays HttpOnly, forwarded only server-to-server.
- No new database migrations, uploaded file changes or chat permissions.

Tests cover plan signing, per-process approval replay, concurrency, user isolation, disabled production behavior, URL
boundaries, rejection of dangerous model actions, and authenticated API
approval. **Live Chromium smoke tests are not part of the standard CI**;
an operator must opt in and verify a public allowed domain with a live LLM
before calling the feature ready for real users.

## Next milestones: real computer-use capability

Move the browser to an isolated, unprivileged, restricted-egress worker;
persist per-user run state and idempotent approvals; add screenshots, pause/
resume/cancel, dynamic JS and website automation with fine-grained per-action
approval, verification and redaction. Desktop control must be a separate
opt-in local companion with narrowly scoped permissions; never run arbitrary
model-supplied shell commands on the user's Mac.

## Bounded multi-page navigation upgrade

Rather than following only a single chain, the browser now tracks a bounded
frontier of up to 60 safe links discovered on visited pages. At each step,
the AI chooses among the first 25 eligible links, including relevant links
found on earlier pages. All candidates must match the operator's exact
HTTPS host allowlist, pass existing blocked-path checks, and remain unvisited.
The task prompt includes visited-page titles and link URL paths as context.
This improves the chance of exploring alternative documentation branches
within the existing four-page, 55-second read-only budget.

This is still **not unrestricted browsing**. The agent does not submit
forms, run page JavaScript, use cookies, change data, or operate desktop
applications. Production deployment is operator-gated and additionally
requires independent SSRF/egress acceptance; no rollout is implied by CI.


## Browser Agent v2 — ranked evidence and resilient read-only navigation (2026-11-01)

- Uses bounded lexical hints from the user's research goal to **rank** the
  prevalidated same-host link frontier before presenting the best 25 choices
  to the LLM. The model can still only choose an enumerated safe link or finish.
  No model-generated URLs, selectors, JavaScript or cross-host operations.
- Strips only known *tracking* query keys (`utm_*`, `fbclid`, `gclid`, etc.)
  and in-page fragments before deduplication. Preserves search, pagination
  and other functional parameters; validates URLs before and after rewriting.
- Production HTML-only mode preferentially extracts `article` / `main`
  content, discarding scripts, forms, menus, headers, footers and asides.
- A broken **secondary** approved page no longer destroys earlier evidence.
  It can skip to another previously approved same-host link. Limits remain
  **4 successful pages, 6 HTTP attempts, 55 seconds** per execution. A broken
  start page fails, invalid model actions fail, and reports still require
  valid `[B1]` style citations against actually visited pages.
- These upgrades are pure backend enhancements to the existing approval API;
  no database migrations, new user permissions or website login are added.
  Unit tests use mocked DNS, fetch and LLM — they do not certify remote-site
  reliability, production provider quotas or network egress isolation.

**Deployment:** keep the existing operator allowlist, Redis approvals and
production HTML-only gates. Review the draft PR and CI first; do not
merge to protected `main`, flip production flags or redeploy Render until
real-site acceptance and rollback checks are complete.
