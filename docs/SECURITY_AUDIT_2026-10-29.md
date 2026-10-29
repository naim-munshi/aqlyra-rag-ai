# Aqlyra RAG AI — Cybersecurity assessment (2026-10-29)

**Scope:** Original `naim-munshi/aqlyra-rag-ai` Core and Full Release branches, GitHub CI evidence, frontend API proxies, FastAPI, PostgreSQL/pgvector, document parsers, JWT/auth, RAG, guest chat, admin and infrastructure configuration. Review conducted with authorized source-code inspection, existing automated tests and **read-only** Neon/Render/Vercel checks. No destructive production penetration test, brute-force activity, load test or recovery experiment was performed.

**Verdict: CONDITIONAL / NOT PUBLIC-LAUNCH CERTIFIED.** Source-level mitigations and exact-commit CI passing are not substitutes for production authenticated end-to-end tests, provider reliability, or an independently audited deployment.

## Critical release gates

1. **Production data and recovery:** Full-schema off-host private backup and isolated restore are mandatory before changing the existing Render Core service to Full. Keep previous recovery branches; do not reset/migrate/downgrade any production data in this review.
2. **Database least privilege / RLS defense-in-depth (HIGH):** A private read-only configuration review identified database role and policy hardening work that must be completed before public release. Do not simply toggle production policies. Validate a separate restricted runtime role, transaction-scoped identity context, owner-scoped table policies and negative authorization tests against isolated staging first. Detailed infrastructure findings and identifiers should remain in owner-private evidence, not in this public repository.
3. **Full public app is not accepted:** Vercel protected deployment and Core Render liveness do not establish live Full feature acceptance. Keep Vercel Authentication on and Guest flag off until the Full backend, private storage, signed guest proxy, Redis and real LLM acceptance pass.
4. **Real identity / provider integration:** Google OAuth and email delivery must be verified independently; email delivery intentionally deferred by owner. No verification bypass. Confirm voice and artifacts against actual providers and persistent storage before launch.

## Threat-model observations

| Attack class | Source evidence | Assessment / remaining gate |
| --- | --- | --- |
| SQL injection | SQLAlchemy ORM `select()/where()`, `plainto_tsquery()`, owner-scoped RAG retrieval; one raw advisory-lock statement uses `text(...:key)` with a bound argument; disposable-Postgres SQL-metacharacter regression tests | **Mitigated at reviewed sinks**, not a guarantee every future SQL query is safe. Include DB permissions and real two-user staging tests. |
| Broken object-level authorization / IDOR | Documents, conversations, memory, Study Abroad and artifact access use authenticated owner IDs; automated two-tenant isolation matrix | **Source/CI evidence positive.** Real multi-user production tests and independent database authorization controls remain release gates. |
| Authentication / session hijack | Signed JWT restricted algorithm, `auth_epoch` logout revocation; HttpOnly Secure SameSite=Lax frontend cookies; OTP attempt/cooldown controls | **Controls present**. Validate live Google identity, real account recovery, signed-cookie/session tests and audit revocation under concurrency. |
| CSRF | Next `/api` middleware rejects untrusted Origin / fetch-site for state-changing requests | **Controls present**; test proxy Host/forwarded metadata assumptions and custom-domain changes before public release. |
| XSS / markdown | ReactMarkdown with `skipHtml`, no message images, links with `rel=noopener noreferrer`; CSP blocks framing/plugins but lacks an enforced nonce-based `script-src` | **Partial mitigation**. Test stored/reflected XSS in previews and generated artifact rendering. Nonce CSP requires a separate compatibility review with Next.js/Google. |
| SSRF / browser tools | Web research uses fixed Tavily HTTPS API, redirects disabled; browser agent validates host and pins public IPv4, **disabled in production** without isolated worker | **Strong current guardrails**. Isolated egress worker and DNS rebinding checks required if enabling browser execution. |
| Uploads, decompression / DoS | Extension + magic verification, ZIP member/expanded byte/ratio limits, image megapixel caps, path normalization and UUID storage keys; new PDF page/text budgets; bounded frontend auth/JSON/multipart bodies | **Improved**. PDF `extract_text()` can still consume CPU before returning; use isolated workers and time/memory budgets for hostile public files. |
| Guest spam / IP spoofing | Signed Vercel-Render request body, per-IP Redis limits, fail-closed behavior, bounded direct Render bodies; fixed 24h IP audit | **Implemented, not live accepted.** No guest launch before real provider/Redis/proxy checks and user-visible disclosure. |
| Dependency supply chain | Automated Python pip-audit, npm audit, static scans; patched `langgraph-sdk==0.4.6` from vulnerable `0.4.4` and upgraded `langgraph==1.2.14` | **CI PASS on audited commits**. Verify deployed container digest and re-run regularly. |
| Operational data leak / monitoring | Admin UUID allowlist and verified account, private no-store responses, sanitized error surfaces and restricted metrics | **Controls present**. Monitor real admin auth/traffic logs and metrics while preserving guest IP 24h lifetime. |
| HTTPS/browser policies | Anti-framing, nosniff and limited CSP; production-only HSTS + Permissions-Policy added to Full frontend | **Defense in depth**; must confirm actual HTTP response headers on newly deployed frontend, not only tests. |

## Acceptance evidence and limitations

- Source-level SQL injection tests use a **disposable** PostgreSQL database. Production DB SQL injection testing has **not** been run.
- GitHub workflows include backend PostgreSQL 16/18, frontend lint/typecheck/build, dependency audits, static security checks, ARM64 full-stack predeploy, documentation and read-only release probe. Record the exact **latest** Full HEAD and 8/8 outcomes before each deployment.
- The existing Render service intentionally uses Core, with auto-deploy OFF. PR #37 must remain Draft/unmerged without explicit owner approval.
- Vercel production protection remains active. Frontend READY does **not** imply Guest chat, RAG, storage or Study Abroad are operational.
- Email sending remains deferred by owner.
- Network/load/DAST, service recovery, two-user production isolation, OAuth browser flow, real malicious document sandbox runs, voice/audio tests, object storage ACL checks and deployment credential rotation are **not** fully verified.

## Next prioritized actions

1. Validate GitHub security commits and then deploy only vetted frontend security changes to the existing **protected** Vercel project. Do not enable Guest or remove SSO.
2. Establish a production-equivalent **isolated staging** database and a restricted runtime identity; design RLS policies and role grants there first. Never trial policies on the only live production database.
3. Run bounded DAST in staging: SQL injection parameterization, IDOR matrix, CSRF, XSS, SSRF allowlist, ZIP/PDF decompression and HTTP request-limit cases.
4. Add automated secret scanning, SBOM/hash-pinned dependency generation and signed container/deployment provenance as feasible on free tiers.
5. Verify post-Full schema backup and isolated restore; cut over Render branch only with release gates satisfied. Re-run live authenticated, privacy, restart persistence and provider tests before public launch.

**Safety:** Keep deployment identifiers, exact unresolved infrastructure weaknesses, credentials, user content and attack evidence in an owner-private security record. This public checklist intentionally avoids operational disclosure and does not certify the service as unhackable.
