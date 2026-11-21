# Aqlyra product demo and acceptance checklist

This walkthrough presents the **real deployed application** separately from the **scripted public portfolio demo**. It is intended for an interviewer, product reviewer, or operator. Do not treat illustrative examples as live retrieval evidence.

| Entry | What it does |
| --- | --- |
| https://aqlyra-ai.vercel.app | Real authenticated production-beta application |
| https://aqlyra-ai.vercel.app/demo | Public, intentionally scripted browser-only architecture/product examples |
| https://github.com/naim-munshi/aqlyra-rag-ai | Actual implementation, CI and review history |

## Five-minute review

**0:00–0:30 — Landing and architecture.** Open the public `/demo` route. Confirm the UI clearly says **SIMULATED CONTENT** and explains that no live LLM calls occur on that page. Switch between Knowledge and Converse; inspect an illustrative source excerpt. Open architecture. Check mobile layout; use a 390-pixel viewport as one test size.

**0:30–1:30 — Live Converse.** Open the real app, sign in with a **test account** and ask: `Explain the difference between lexical and semantic retrieval in three sentences.` Follow up with: `Now give a Japanese one-sentence summary.` Capture an anonymized answer and UI state. This tests session continuation and language handling; it does not establish long-term memory quality.

**1:30–2:15 — Live Web Research.** Ask: `What changed recently in the official Python release notes? Give source links and explain the publication date.` Use Web On if available. Inspect the returned URLs, dates and relevance. Check at least two independent authoritative sources; do **not** treat a citation marker alone as verification. Current production search provider is Tavily. The keyless SearXNG canary is independent and should not be advertised as a general index.

**2:15–3:45 — Private Knowledge.** Create a *synthetic and non-sensitive* PDF containing exactly:
> Sample support hours: Monday through Friday, 09:00 to 17:00 JST. Support is closed on Saturday and Sunday. For urgent issues use the sample ticket queue.

Upload as account A and wait for successful indexing. Ask: `When is support open, and which document states it?` Inspect the cited excerpt. Ask: `What is the refund deadline?` The correct behavior is to say the selected document does not establish that deadline, not invent one. Repeat access using account B; B must not access A's file even if it knows its identifier. A production PASS requires an actual 404/403 result, not merely a hidden UI control.

**3:45–4:30 — Voice.** If the actual Vercel release contains browser speech fallback and the device offers `SpeechRecognition` plus `speechSynthesis`, grant microphone permission only for the test. Speak a short non-sensitive prompt and inspect the persisted user and assistant turns. Test mute, end and permission denial. Browser speech recognition may use device/browser-vendor servers. If unsupported, record **BLOCKED**, not PASS. LiveKit RTC requires a separate joined agent and is not established by this test.

**4:30–5:00 — Trust and scope.** Explain owner-scoped JWT auth, Redis rate limiting, cloud upload checksums, the isolated semantic worker and the source/citation validation layers. Show CI. State that Browser Agent production execution remains disabled until a distinct browser sandbox/egress gate is validated. Do not stage an unsafe browsing demo using production credentials.

## Evidence matrix for a release review

| Scenario | Acceptance evidence | Current claim |
| --- | --- | --- |
| Public demo | Explicit scripted label; example prompts; browser-only architecture | UI source exists; live /demo URL must be checked after deployment |
| Converse | Two sequential real messages, context preserved, response visible | Production LLM reachable, full user E2E outstanding |
| Web | Real search, relevant URLs, dates, response and citations | Provider canary PASS, broader answer quality outstanding |
| Knowledge | Synthetic file uploaded, 384-d vectors, citation to file and fail-closed unsupported answer | Existing PDF 12/12 vectors; new-upload E2E outstanding |
| Private access | Account B denied Account A's file and project | CI tests exist; live two-user E2E outstanding |
| Voice | Browser supported, permission, speech input/output, persistence | Conditional feature; browser/device E2E pending |
| Browser Agent | Container/VM isolation, egress firewall, replay-safe approvals, adversarial tests | Disabled in production |
| Backup | Verified off-host DB/object export + isolated restore | Recovery branch only, **not PASS** |

Record date/time, frontend/backend deployment SHAs, expected behavior, actual behavior, PASS/FAIL/BLOCKED, and redacted test evidence. Do not copy credentials or private user text into issues.

## Demo materials, not production credentials

You can make the sample file with any PDF authoring application or with your test environment's PDF tooling. Do **not** use real personal records, workplace data, medical records or immigration documents.

For portfolio screenshots include a clear legend:
- **LIVE** — redacted authenticated request actually executed against production.
- **SCRIPTED** — manually authored scenario data and simulated source excerpt.
- **CODE VERIFIED** — automated unit/integration test, not a user-visible live result.
- **BLOCKED** — required provider or infrastructure missing.

There is **no recorded video artifact** certified by this repository yet. Produce one only after the actual test steps are observed, with secrets and account identifiers redacted. Do not describe a script or storyboard as a finished recorded demo.

## Development verification

~~~bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit
node --experimental-strip-types --test tests/*.test.mjs
npm run build
~~~

Backend tests require a dedicated disposable PostgreSQL test database:

~~~bash
cd backend
python -m pytest -q
~~~

Use [PRODUCTION_STATUS_2026-10-31.md](PRODUCTION_STATUS_2026-10-31.md) and [RELEASE_ACCEPTANCE.md](RELEASE_ACCEPTANCE.md) for anything not verified.
