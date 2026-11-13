# Aqlyra — Full-System Verification (12 November 2026 JST)

**Scope:** Read-only production/API/UI probes plus review of *executed* exact-release GitHub Actions tests. This report is a time-bounded test record, **not** a production certification, a high-volume live load test, or an assertion that CI source has been deployed on Render. No customer documents, account secrets or production writes were used.

## Immutable test targets

- Backend source release: `release/core-without-study-abroad-20261027` at `256cdd72714dc3444ac21fe62896b13e03acc91b`.
- Frontend Vercel production: `aqlyra-ai.vercel.app` READY, deployed commit `ba0ed757d752607c540861741716797c8fdbe562` on `fix/center-empty-chat-composer-20261102`.
- Production backend: `https://aqlyra-api-free-launch.onrender.com`; **exact deployed SHA not proven**. Current public readiness lacks `deployment_git_sha`, notwithstanding [PR #196](https://github.com/naim-munshi/aqlyra-rag-ai/pull/196) merged in source. Render management connection unavailable during this audit.
- Voice worker: Railway `Aqlyra-Staging` / staging / `aqlyra-voice-worker`, reported online 1/1 replica, 0 critical incidents in 24h; no real microphone E2E evidence.

## Executed source/CI checks (same release SHA)

- GitHub [16/16 successful check runs](https://github.com/naim-munshi/aqlyra-rag-ai/actions?query=branch%3Arelease%2Fcore-without-study-abroad-20261027), including SAST, Python/npm dependency audits, frontend security, Docker, native ARM64, static semantic model inference, and production build.
- PostgreSQL 16 and 18: **1,309 tests passed and 12 warnings on each database run**, no failures. These are the same backend test cases exercised under two database versions, not 2,618 distinct tests. [PG16 job](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/43070358591/job/130696263930) / [PG18 job](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/43070358591/job/130696263250).
- Frontend lint/type/build successful; 46 automated frontend tests passed, 0 failed ([frontend job](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/43070358556/job/130696262956)). CI has non-failing Node module-format/deprecation warnings.
- Disposable native ARM64 full-stack (Caddy, frontend, FastAPI, PostgreSQL/pgvector, Redis) passed two-user RAG/ownership checks, cross-origin denial, 20-request low-rate performance probe, and **local** DB/upload restore rehearsal. This is not an independent off-host encrypted production recovery proof.
- Disposable two-user real HTTP RAG E2E passed synthetic ownership, conversation isolation, upload, parsing, vector DB indexing, grounded citation/refusal **with a deterministic response provider**. Real Groq answers and real account email verification were not tested.

## Simulated concurrent chat capacity — NOT live Groq/RAG capacity

GitHub [0.1 CPU / 512 MiB benchmark](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/43069505106/job/130693251340) explicitly matches Render Free's published CPU/RAM envelope, but runs Docker on isolated CI loopback with local PostgreSQL, deterministic responses, no rate limits, and no external providers.

| Simultaneous synthetic HTTP users | Success | p95 latency |
| ---: | ---: | ---: |
| 10 | 10/10 | 1.277 s |
| 25 | 25/25 | 2.596 s |
| 50 | 50/50 | 5.337 s |
| 100 | 100/100 | 9.844 s |

One short chat turn per account per tier; 185/185 succeeded. Do **not** advertise '100 real AI users' based on these measurements. Per-process chat admission defaults to **12 in-flight requests** + a **10-second queue**; then returns safe 503. Groq token/RPM quotas, 384D worker wake-up, Neon network pool, memory, provider latency and voice have not been represented in this benchmark.

## Live read-only API and infrastructure

| Probe | Observed | Verdict |
| --- | --- | --- |
| Direct Render `/api/v1/health` | HTTP 200, status `healthy` | PASS for liveness *at probe time* |
| Direct Render `/api/v1/readiness` | HTTP 200, status `ready`; database and Redis `ready` | PASS for dependency probe *at probe time* |
| Vercel `/api/health` | HTTP 503 on first read, later HTTP 200 `ready` | **FLAKY**; possible Free instance spin-down or 10 s frontend proxy timeout, unconfirmed without Render logs |
| Semantic worker `/health` | HTTP 503, then HTTP 200 `ready` with `bekko-static-multilingual-int8-mrl384-v1`, 384 dimensions | **FLAKY first request**, recovery observed |
| SearXNG candidate `/health` | 503 initially, subsequently 401 without credentials | **NOT VERIFIED**; access-controlled status does not prove search success/failure |
| Anonymous `/api/v1/users/me`, `/documents`, `/artifacts`, `/metrics` | HTTP 401 each | PASS: unauthenticated resource access denied; not an authenticated cross-tenant test |
| Backend reported `artifact_storage` | `ephemeral_test_only` | **BLOCKER** for persistent generated artifacts |
| Backend reported `cloud_uploads` | `private_proxy_configured` | Configured only; no live upload/download success assertion |
| Backend reported `public_web_research` | `configured_unverified` | **NOT VERIFIED** for real provider answer quality |
| Railway LiveKit worker | Online, 1/1 replicas; a few warnings in observed logs | Process availability only; **no real mic conversation** tested |

## Public website black-box regression

- Read-only signed-out real browser visited `/`, `/about`, `/how-it-works`, `/demo`, `/help`, `/login`, `/register`, `/forgot-password` and `/study-abroad`. Public navigation/load showed no visible blank-screen failure.
- Login and register show Google and email/password options, but no real OAuth/password transaction was performed. A visible button is not proof of working sign-in.
- `/demo` is expressly **scripted**, not live inference. `/study-abroad` redirects signed-out users to login as implemented. `/guest` also showed login rather than live guest AI; guest route availability depends on feature flags and is not currently an accepted guest-chat path.
- The browser agent *initially* reported `/forgot-password` redirect and misspelled brand logo. Follow-up direct Vercel HTML GET returned **HTTP 200 with 'Reset your password' form**, and actual logo source spells `Aqlyra`; **do not classify those agent observations as confirmed defects**.
- `robots.txt` and `sitemap.xml` returned HTTP 200; sitemap contains five public URLs. This is crawl configuration, not search ranking proof.

## Model-quality evidence: retrieval ≠ answer quality

- Actual shipped static semantic ONNX weights evaluated offline on 60 author-translated **synthetic** EN/JA/BN queries: Hit@1 **70% English / 35% Japanese / 60% Bengali**; Hit@3 **90% / 55% / 75%**. [Real-worker CI](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/43070358571).
- Japanese recall is a meaningful retrieval-quality gap. No trusted **live** Groq completion, grounded answer accuracy or citation precision scorecard was produced here; examples rendered by the demo do not count.

## Release blockers and next acceptance gates

1. **P0:** Reconnect Render management access; compare actual deployed Render SHA with release SHA. Deploy a reviewed release only with a rollback plan. Repeat readiness/cold start with sanitized logs.
2. **P0:** With *authorized* disposable verified accounts, test real registration, OTP, Google OAuth, password reset, chat/stream, upload, Knowledge PDF/image OCR, Study Abroad, owner A vs B document/citation/memory/isolation, and logout/session revocation on live staging or approved production.
3. **P0:** Put generated artifacts and originals on confirmed durable storage, then execute independently encrypted off-site backup **and isolated restore**. A passing local CI restore does not satisfy this.
4. **P1:** Evaluate real Groq web research and multilingual RAG against independently labeled evidence, refusals, citation support and provider 429/503 behavior. Improve Japanese retrieval before quality claims.
5. **P1:** Measure actual provider-backed 1/2/5/10/25-user streaming and Knowledge latency/error/quotas on isolated staging with a controlled budget and low-risk rollout. Do not run 100-user production load without approval.
6. **P1:** Perform real iOS and desktop microphone→LiveKit→STT→LLM→TTS→interrupt/hang-up test. Railway worker Online is not equivalent to this gate.

**Status vocabulary:** `PASS` = explicitly executed and observed in specified scope; `FLAKY` = contradictory consecutive live observations; `NOT VERIFIED` = insufficient access/evidence; `BLOCKER` = prevents asserting production-ready. No item in this report certifies commercial scale, human-level answer accuracy, unrestricted guest chat, or production data recovery.
