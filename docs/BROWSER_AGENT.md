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
- Disabled by default, including **always disabled in production** until a
  separately sandboxed browser worker, egress ACLs, quotas, and durable
  approval/replay storage are deployed and security reviewed.
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
- Each approval is **single-use within one local API process** and lasts
  at most 120 seconds. A process restart clears the replay ledger; separate
  workers do not share it. Production stays disabled until a durable,
  centrally enforced single-use approval store exists. The local runner
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
