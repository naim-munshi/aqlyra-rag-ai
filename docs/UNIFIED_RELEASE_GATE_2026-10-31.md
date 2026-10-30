# Aqlyra unified release gate — 2026-10-31

**Draft PR #58** is a source integration candidate, not production approval.
It is stacked on RAG PR #57 and Core PR #36. This is the existing
`naim-munshi/aqlyra-rag-ai` project, not a replacement repository.

## Exact source evidence

- Core source: `d5a6540fb3a9a8c521036bc86eebf48b3201900e`
- RAG enhancement: `9f82391172780500a9596c3758b4eb1cb79ce8de`
- Last verified production Vercel UI source:
  `92edb4ee951ff49a99d8980df3558087ec3b3a30`
- Unified branch: `release/unified-core-frontend-rag-20261031`
- The candidate retains the live frontend's Converse, Knowledge, mobile,
  Study Abroad, upload and in-chat file generation UI; Core RAG, OCR,
  rate limits and secure storage; and the opt-in signed guest and remote
  artifact service. All high-risk optional capabilities remain gated.
- A new 7/7 GitHub workflow result is required on **the exact candidate
  SHA** after every change. Old CI results do not authorize a release.

## Required independent production acceptance

| Gate | Required observed PASS evidence |
| --- | --- |
| Auth | Real Gmail OTP delivery/expiry/replay, Google sign-in, password reset and two-user isolation |
| Document lifecycle | 50 MiB S3 PUT/finalize/re-download/restart, owner-only recovery, deletion and integrity |
| Knowledge | PDF/OCR -> queued -> ready -> source-grounded answer, multilingual accuracy, real 384-dim vector provider |
| Web | Live sourced Auto/On/Deep/Off calls, no leaked private context or invented sources |
| AI files | Five formats, consent, owner-only download/restart/delete, signed metadata and real remote storage |
| Voice | LiveKit worker and authenticated mobile microphone/audio roundtrip |
| Browser agent | Isolated sandbox, network egress ACL, durable consent and prompt-injection review |
| Guest | Signed Vercel proxy, Redis budget, no user document access and approved IP retention policy |
| Study Abroad | Current official sources, nationality-specific review, schema and cross-user checks |
| Backup | Encrypted off-host PostgreSQL + private uploaded S3 files + generated S3 artifacts and **isolated restore test** |
| Operations | p95/error/rate-limit load probes, spend/alerts, owner, RPO/RTO and rollback rehearsal |

## No-data-loss rules

- Never merge unreviewed PRs directly into protected `main`, force-push,
  drop/replace the live database, delete private S3 objects or clean orphan
  uploads without an explicit owner-approved recovery plan.
- The Docker-local `scripts/ops/backup.sh` is **not a Neon production
  database/S3 backup**, and a synthetic CI restore is not a live off-host
  recovery test. Neon snapshot quota exhaustion remains a blocker.
- Do not expose credentials, client message text or raw user documents
  in CI logs, GitHub comments or release evidence.
- Do not enable `ARTIFACT_REMOTE_STORAGE_ENABLED`,
  `CLOUD_UPLOAD_PUBLIC_ENABLED`, `GUEST_CHAT_ENABLED` or
  `BROWSER_AGENT_ENABLED` merely because source/CI tests pass.
- A READY Vercel deployment proves a build, **not** Gmail, Hugging Face,
  Tavily, LiveKit or private storage acceptance. `/readiness` explicitly
  reports that live embedding credentials/quota are **not checked**.

**Release decision: BLOCKED** until independent owner-approved external
acceptance is recorded for the exact candidate. No implied production
deployment, merge or deletion follows from this document.
