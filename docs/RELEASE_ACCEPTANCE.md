# Aqlyra final release acceptance and operating handoff

**Repository:** `naim-munshi/aqlyra-rag-ai` only. This is the **full-stack**
application, not the separate `aqlyrax` Vercel portfolio demonstration.

**Source candidate:** Draft PR #33
(`integration/security-release-candidate-20261026`), pending owner's
review and acceptance. Production is **not** live until all external
acceptance gates below are verified on the exact release commit.

## What the automated checks have established

The integration branch has a CI-backed baseline for Python/Postgres,
JavaScript/Next.js, high-severity Python SAST, audited dependency pins, an ARM64 Caddy -> Next.js ->
FastAPI -> Postgres/Redis smoke, fresh-volume Docker readiness,
owner-scoped RAG/auth, generated Office files, Study Abroad, and browser
agent fail-closed behavior. **Always verify the current head's checks**,
not the earlier passing SHA. A mocked LLM response is not proof of
provider-backed factual accuracy, and a disposable backup is not a
production off-host restore test.

## GitHub release gate (read-only, fail closed)

On a checkout of the intended release branch:

```bash
python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
python3 scripts/ops/release_gate.py --json
```

The release script verifies that (1) `main` reports protected and
(2) all seven required workflows completed successfully against the
**exact** current release branch HEAD. It has no ability to deploy or
approve production. It deliberately reports `production_approved=false`.

The owner must use [GitHub Rulesets](https://github.com/naim-munshi/aqlyra-rag-ai/settings/rules)
to apply an **active** `main` ruleset, require pull requests/reviews
and the six checks, restrict deletions/force pushes and verify rules
are enforced (including bypass permissions). A green GitHub workflow
named "Merge Gate" **does not** protect an unprotected branch.

## Production readiness: mandatory external checks

Record who tested, timestamp, release SHA, sanitized output, and
pass/fail for each gate in Issue #34 (never paste real credentials,
passport scans, raw user messages or medical records).

| Gate | Required proof |
| --- | --- |
| DNS/TLS/Caddy | Real HTTPS origin has valid TLS, security headers, and only reverse proxy exposed; backend, Redis and DB are not public |
| Environment | `APP_ENV=production`, real LLM and semantic embedding configured; no deterministic test providers, debug or weak secrets |
| Email identity | Two actual accounts: register/verify, reject pending-email credential replacement, SMTP retry/expiry, login/refresh behavior |
| Google sign-in | Actual authorized Google Client ID; verified audience/issuer/subject flow; refuse invalid credentials |
| JWT revocation | Copied token rejected after logout/reset; other user remains logged in |
| Private RAG | Real-file ingest/OCR/embedding, retrieval quality with cited answers; no cross-user documents in responses; unsupported claims refused |
| AI Files | Create and download actual DOCX/XLSX/PPTX/PDF/MD, enforce cross-account 404, delete/version, require fresh consent whenever source selection changes |
| Study Abroad | Test nationality/residence/destination and program applicability against *current official university/embassy pages*; cite exact document and last-checked date |
| Browser Agent | Remain production-disabled until separate OS/container isolation, egress firewall, durable approvals, prompt injection/SSRF review |
| Migrations | Rehearse `f18a3c42e917` then `d4ec2f9b7860` using a **restored disposable database** and backed-up uploads, not a live wipe |
| Backups | Encrypt and test an off-host backup (Postgres + uploads + private artifacts) and record RPO/RTO/retention/restore owner |
| Language rendering | Inspect Japanese, Bangla, Arabic and mixed-script files on real Office/PDF clients; PDF glyph/shaping support may fail |
| Performance | Synthetic load, p95 latency, error/rate-limit behavior, memory/CPU quotas and provider spend |
| Monitoring and rollback | Verify alert delivery, health checks, log redaction, rollback build and incident ownership |

The Browser Agent and artifact renderer run under limited development
guardrails, **not a complete isolated worker sandbox**. Do not enable
untrusted public browser automation until network egress and worker
isolation are independently demonstrated. Review retention,
data deletion, backup encryption and external AI model provider terms
before collecting sensitive student case files.

## Non-destructive staging procedure

1. Create a **new staging host/project** dedicated to
   `aqlyra-rag-ai`, using a disposable database and isolated
   persistent volumes. Never attach your current Mac's production
   Docker volumes or a real user database.
2. Configure private secrets on the host or provider secrets manager;
   never commit or paste actual `.env.production` values.
3. Back up and verify uploads and the disposable database. Run the
   existing `scripts/ops/production-preflight.sh` using the host's
   private production-like env file; do not rely on the sample env.
4. Use the project's production Compose profile and Caddy DNS/TLS
   instructions in `docs/STAGING.md`, with public DB/API ports
   blocked, then run:
   ```bash
   python3 scripts/ops/staging_smoke.py --base-url https://YOUR_STAGING_DOMAIN
   ```
5. Test each gate above with two independently created accounts.
   Confirm no unauthorized data leaves the selected tenant. Record
   only sanitized outcomes in Issue #34.
6. On failure: halt the rollout, preserve logs (without PII), fix in a
   **new PR**, rerun exact-head CI and staging acceptance.
7. Only after evidence is complete should the owner approve merging
   the reviewed branch and scheduling a controlled production release.

## Known deferred product decisions

- No billing backend exists: no paid tier is advertised in the release
  candidate. The Help page is an informational page, not a support
  ticket system.
- Full interactive Office WYSIWYG editing, multi-language PDF shaping,
  unlimited artifact generation, true background job queues,
  source-specific visa guarantees and unrestricted browser automation
  are out of scope for the pre-production core.
- `main` has been left unchanged until owner-controlled branch
  protection, staging acceptance and explicit merge approval.

## Incident and rollback contacts

Owner must nominate a human for on-call response, alerts, database
backup and rollback. On suspected leakage or compromise, disable
public ingress, rotate exposed credentials, revoke sessions, preserve
forensic logs securely and recover only from independently verified
backups. No script in this repository should automatically wipe live
database/upload volumes or silently roll back migrations.
