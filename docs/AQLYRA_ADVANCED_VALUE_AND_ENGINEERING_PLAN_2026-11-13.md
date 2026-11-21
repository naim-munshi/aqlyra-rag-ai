# Aqlyra — Advanced Value & Engineering Plan
**Prepared:** 2026-11-13 JST  
**Scope:** existing Aqlyra RAG AI; do not rebuild, delete customer data, merge unrelated PRs, or weaken protected main.  
**Current status:** reviewed and staged code changes ≠ production acceptance.  
**Evidence:** current Vercel commit d149b088, Render API/Core 14cf64f7, semantic worker 313d4ee5; protected main 6bd16d5f remains behind. See [technical audit](INTELLIGENCE_ENGINEERING_AUDIT_2026-11-13.md).

## 1. Product thesis: value over raw chatbot imitation

**Initial buyer:** a small or mid-size company with scattered HR policies, operations manuals, technical runbooks and customer-support articles. Their actual pain is time lost locating the right policy revision, conflicting answers, permission-sensitive data, or replying without an authoritative source.

**Useful product promise, not an established claim:** a private multilingual knowledge copilot that (1) finds the relevant authorized policy quickly, (2) answers with inspectable quotations and document location, (3) states uncertainty or conflicts, and (4) can later complete a human-approved workflow. Aqlyra should compete on **verified organizational knowledge + permissions + task completion**, not on pretending to be a frontier foundation model.

**First repeatable workflow (pilot):**
- Admin imports an owner-approved handbook, technical manual and FAQ into a workspace.
- Staff asks in Bengali, Japanese or English: “How many personal leave days?”, “How often does HM-72 measure?”, “Which revision is effective?”, “Compare the refund processes.”
- Aqlyra gives a short direct answer, clickable source excerpts, source document/version, and where the relevant answer came from.
- When the source is missing, contradictory, expired or not accessible, Aqlyra refuses or identifies the unresolved issue rather than inventing a rule.
- A future permissioned connector can create a support-ticket or draft an email *only after explicit authorization*.

**Second use case (after first works):** source-verified Study Abroad program-fit analysis, separating known official requirements, unverified unknowns, applicant-provided facts, and missing eligibility evidence. No invented probabilities or guaranteed admission/credit transfer.

## 2. Why present-day Aqlyra feels less intelligent

| Area | Verified implementation reality | Failure mode | Proper remedy |
|---|---|---|---|
| Model | Groq/OpenAI adapter, one normal configured model, default 800 output tokens in Core | Complex work truncated or oversimplified; model/effort configuration not measured live | Explicit opt-in quality model routing; A/B comparison; output-token and quota budgets |
| Continuity | Last 20 recent messages + optional memory, originally without bounded serialized context | Long context can exceed quota, omit user intent, or fail on 429 | PR #95 UTF-8 budget, current-message preservation, explicit omitted-context flags |
| Search | Hybrid 384D pgvector + PostgreSQL lexical, RRF and Unicode fallback | Remote embedding 429 / missing index; FTS English distractor suppresses Japanese/Bangla evidence | Reindex coverage, lexical-only labeling and mixed-script fusion on Core |
| Grounding | Source-validated citations and refusal, optional LLM verifier | A syntactically correct [S1] can still support an incorrect claim | Human-labelled support checks, optional verifier only after latency/accuracy test |
| Research | Opt-in public research, bounded browser, exact calculator | Tools not always enabled/available, current claims can be stale | Reliable source checking, provenance, guarded tool choices |
| Memory | Owner-scoped semantic memory with optional lexical fallback | 429 / unindexed memories / stale facts | Opt-in, cost-aware memory, user correction and expiry, isolation tests |
| Deployment | Vercel frontend from separate branch; Render Core backend; historical main | Stale releases, features existing only in PRs, unpredictable user experience | Single deployment inventory and reviewed release train |
| Voice | LiveKit/Railway integration; free cloud migration prepared | Trial/worker offline; a connected room is not necessarily a joined AI agent | Reuse exact LiveKit project, deploy managed worker, real iOS audio acceptance |

### Concrete change sets already staged

- **PR #95** normal conversation budget: max **32,768 UTF-8 bytes** for prior context where the current request is within that limit; keep the current message intact even if large. Standalone greetings skip redundant memory embedding and extraction calls. Added flags `history_truncated` / `memories_truncated` so the model does not hallucinate recall.
- **PR #95** optional **Quality Model Routing**: deterministic English/Bengali/Japanese complex-task trigger, same configured Groq credentials, allowlisted `openai/gpt-oss-120b`, 1,600 completion-token cap, no automatic SDK retry. Default `LLM_QUALITY_ROUTING_ENABLED=false`. No new external tools, no extra LLM classifier request; current normal-chat streaming/generation share the same routing point. This is *not yet a measured quality win*.
- **Core release PR #36 branch** optional **mixed-script FTS + Unicode retrieval fusion**, scoped to authenticated owner and requested documents, deduplicated weighted RRF, raw lexical score kept separate from ranking score. Default `KNOWLEDGE_MULTILINGUAL_UNICODE_FUSION_ENABLED=false`, with real Postgres isolation tests. More database work per multilingual query; enable only after performance acceptance.

## 3. Release sequence: hard gates, not feature-count goals

### Gate A — trustworthy baseline, no product rewrites
1. Inventory exact frontend/backend/semantic/voice SHA, deployment IDs, feature flags and rollback source; record them in release notes. **No secrets or raw private content.**
2. Reconcile *existing* source branches and PR dependencies; current Core PR #36 and Frontend PR #101, separate Voice PR #205, security pin PRs #147/#149. Do not merge historical 48 PRs en masse.
3. Demand passing full PR-head CI, independent reviewer where protected main requires it, and real non-admin + admin sign-in path checks.
4. Capture anonymized health metrics: 4xx/5xx breakdown, p50/p95, upstream 429, search-mode fallback, context truncation, tokens per answer, and retries. Keep raw customer prompts out of telemetry.
5. Prepare rollback for frontend SHA/backend SHA and a zero-data-loss DB backup rehearsal before operational changes.

### Gate B — answer continuity & latency
1. Review and integrate PR #95 only into its intended Core release using the normal checks. Measure truncated-history frequency and provider context errors with 1, 2 and 5 synthetic concurrent conversations.
2. Introduce opt-in stronger model routing *after* an A/B experiment on a held-out corpus; keep the single-call base model for basic questions and low quotas. Never auto-upgrade the Groq plan.
3. Investigate 429 root cause separately for Groq and semantic ONNX ingress. Count explicit rejected requests and route status, not only user-perceived slowness.
4. Preserve consistent SSE behavior, no duplicate messages, no invisible model retries, no abandoned DB sessions.

### Gate C — highly accurate private RAG
1. Measure **current embedding coverage** on tenant-scoped ready chunks: current 384D vector count / eligible chunk count; distinguish partially indexed, provider-error, zero-vector, and ready documents. Do not pretend lexical-only retrieval is semantic.
2. Reindex missing vectors in idempotent small batches with configured backoff and a bounded quota. Never bulk reindex production without explicit acceptance and rollback.
3. Compare lexical, dense, hybrid, hybrid+rerank and hybrid+rewrite under identical labels/K/latency. Run mixed EN/JA/BN corpus with negative and cross-account adversarial cases; verify partial-source and evidence conflicts.
4. Evaluate source support **at claim level** (not citation syntax alone); prefer short, evidence-specific responses and support useful partial answers.
5. After Core mixed-script fusion passes a real data-size benchmark and leakage regression, allow a bounded staged flag rollout.

### Gate D — actual work completion, not decorative agents
Add *one tool at a time* under explicit schemas and user/tenant permissions:
- Read-only: internal approved policy search, document metadata/version lookup, sourced public-web research, deterministic calculator.
- Write/action proposals: create draft support reply; preview tool arguments and affected tenant/account; user confirms before sending or modifying anything.
- Later connectors (e.g. Google Drive/Notion/Slack/SharePoint) must use scope-limited OAuth, revocation, incremental sync, source ACLs, deduplication, audit trails and consent. These are **not implemented today**.
- Stop after bounded tool turns/timeouts; never execute model-written shell or SQL against production.

### Gate E — voice/mobile & robust operations
- Reuse LiveKit Cloud Build free plan: quota **1,000 agent minutes/month**, limited inference credit and concurrency, not unlimited production. Cold starts, microphone permissions and agent dispatch require real-device tests.
- Run owner-authorized English, Bangla, Japanese and code-switching calls, interruptions, background tab, disconnect/rejoin, sessions from two accounts, and STT/TTS quotas.
- Add admin-only *non-content* diagnostics: deployment version, indexing %, provider failure counts, quota & active voice sessions; no public user-email disclosures.
- Benchmark realistic 1/2/5 user workloads; Render Free cold start and Groq rate limits prevent unconditional concurrency promises.

## 4. Measurable acceptance scorecard — targets, not achieved claims

| Metric | Baseline source | Proposed pilot acceptance goal |
|---|---|---|
| Private-document Hit/Recall@5, nDCG | Versioned labelled pilot corpus, per language | Recall@5 >= 0.85, nDCG@5 >= 0.80; compare vs original |
| Claim-level cited answer support | Independent manual double review, 3 languages | >= 95% supported substantive claims on eligible questions |
| Refusal correctness | Answerable and unanswerable fixtures | >= 90% correct refusals, lower false-refusal than baseline |
| Answer quality | Blind baseline vs candidate scoring (accuracy, usefulness, language, brevity) | Material and repeatable improvement without safety regression |
| Grounded privacy boundary | Two independent identities, wrong-doc IDs, prompt injection in docs | **0 cross-tenant information leaks** |
| Connected warm p95 | Authorized staged sessions, report cold separately | Aim <= 8s for small RAG queries; measure instead of claiming |
| Cost/throughput | Provider tokens, retry counts, rate-limit metadata | Stay within explicit free quotas; show rate-limit errors clearly |
| Voice acceptance | Real Safari/Chrome WebRTC, worker logs | Agent actually joins, STT/TTS speak and interrupt; no silent fallback |

**Required negative tests:** prompt injection in uploaded docs and web results; conflicting policy versions; Unicode/romanized mixed-language phrasing; a signed-in user referencing another owner's document; citation referencing nonretrieved evidence; 429/timeouts; zero vectors; stale memory; recent-date claims without public research; heavy/long conversations; unreviewed write tool request.

## 5. Budget and capacity truth

- Groq's published Free rates include organization-wide limits around 30 requests/minute, 1,000/day and 8K tokens/minute for the GPT-OSS 20B/120B entries, but **account-specific limits are authoritative**. A long prompt can exhaust the token budget with much fewer than 30 calls. [Official limits](https://console.groq.com/docs/rate-limits) / [models](https://console.groq.com/docs/models).
- LiveKit Cloud Build limits active agent sessions, session-minutes and inference credits; monthly free allowance exhaustion is a hard stop, not infinite usage. [Quotas](https://docs.livekit.io/deploy/admin/quotas-and-limits/).
- Render Free instance cold starts and 512 MiB ceilings can dominate latency. Document warm/cold separately; avoid running a full encoder in the web service if the isolated worker has already been accepted.
- A production business requires a real cost model before multi-tenant paid launch: per-request cost (LLM, embedding, TTS, remote web), support, data retention, egress, quotas and alerting.

## 6. Value validation: which customers will pay?

Run a bounded opt-in pilot with a small set of authorized internal documents, with consent and without private real-user data in GitHub. Measure 3 workflows:
1. **Policy Q&A:** employees' time to find a source-correct rule, answer usefulness, mistakes prevented.
2. **Support resolution:** time to draft an evidence-cited answer with human approval, reduction in reopened tickets.
3. **Technical runbook search:** finding current incident instructions with version/date and permission correctness.

For each workflow record: baseline without Aqlyra, task completion %, median time, source trust, fallback/429 rate, and whether a human would choose Aqlyra again. A lower generic-chat benchmark score is less important than proven time saved on these workflows. **Do not claim time savings until the pilot is measured.**

## 7. Stop/go rules

**Ship** a change only when exact-commit automated tests, source isolation, acceptable p95/rate limits, versioned release notes and a rollback are present.  
**Rollback** if claim-level hallucination, leakage, API 5xx, provider 429 or latency measurably worsens.  
**Do not do:** brand-new architecture rebuild, unconstrained autonomous browsing, unreviewed database migration, blind switch to larger model, exposure of raw logs/user text, deleting old PRs/data, or bypassing independent code review.

## 8. Immediate handoff artifacts

- Core RAG code: [PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36).
- Prompt and model-routing code: [PR #95](https://github.com/naim-munshi/aqlyra-rag-ai/pull/95).
- Live frontend: [PR #101](https://github.com/naim-munshi/aqlyra-rag-ai/pull/101).
- Free LiveKit plan: [PR #205](https://github.com/naim-munshi/aqlyra-rag-ai/pull/205).
- Prior technical audit: [INTELLIGENCE_ENGINEERING_AUDIT_2026-11-13.md](INTELLIGENCE_ENGINEERING_AUDIT_2026-11-13.md).

The current deliverable is staged implementation + safety tests + a measurable release roadmap, **not** a claim of deployed ChatGPT/Claude-equivalent intelligence or completed production pilots.
