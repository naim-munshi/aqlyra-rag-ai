# Aqlyra Security Assessment — 2026-11-08

**Scope:** Existing Aqlyra API deployed on Render, official Next.js BFF on Vercel, GitHub release branch, and reviewed RAG/document/agent code. **Method:** source inspection, existing CI/security tests, and 19 low-impact, unauthenticated HTTP requests sent from a disposable isolated test environment. **No brute force, high-volume DoS, malicious uploads, tenant data access, or privileged account actions were performed.** No production credentials were used.

**Backend live release:** `61cc328f91aabd42ac3d9e94183658b136d939a1`; **official frontend release:** `3f5563e660900e897bb48c31eb3970709c722a0d`. Availability and configuration are point-in-time observations.

## Observed live behavior

| Control | Evidence | Result |
| --- | --- | --- |
| Admin overview and admin account inventory | Anonymous GET of both backend routes | HTTP 401 |
| Documents, memories, projects, conversations | Anonymous GET of each API route | HTTP 401 |
| Public research, browser-agent planning, artifacts, voice | One anonymous request per protected route | HTTP 401 |
| Invalid JWT | Synthetic, invalid Bearer token on /users/me | HTTP 401 |
| Cross-site browser-origin state change | Synthetic request against frontend conversations | HTTP 403 from global Next.js proxy |
| CORS | Untrusted-origin OPTIONS on backend auth endpoint | HTTP 400, no Access-Control-Allow-Origin |
| Swagger / OpenAPI | Requests against backend /docs and /openapi.json | HTTP 404 in production |
| Main frontend security headers | Public health endpoint | HSTS, nosniff, frame denial and baseline CSP present |
| Health | Official BFF /api/health | HTTP 200 at assessment |

**Important boundary:** These requests verify unauthenticated access control and basic edge behavior, **not** a successful account compromise test, stored XSS reproduction, credential stuffing resilience, a vulnerability-free dependency tree, or two-user E2E authorization.

## Audited code controls (not independently accepted end-to-end)

- Private RAG queries and indexed source records are scoped by user ID. Synthetic existing tests cover cross-account document, memory and conversation access, unknown IDs, and citations.
- Authentication bearer validation uses signed access JWTs, explicit token type, per-user auth-epoch revocation and verification state. Tests cover invalid signature, expired tokens and non-interchangeable ticket types.
- Frontend `src/proxy.ts` applies `hasTrustedRequestOrigin` globally to `/api/:path*`, with a narrow internal semantic relay exception. Production cross-origin POST was rejected. Per-route absence of the helper is not alone proof of a CSRF vulnerability.
- Browser Agent is feature gated and requires user-bound signed approvals; DNS pinning checks private IPs. Existing tests cover private/mixed DNS, replay rejection, tenant-bound approvals and Redis failure.
- Public HTML reader pins public DNS and HTTPS, rejects redirects, scripts, large/compressed responses and private/reserved IPs.
- Upload adversarial tests cover fake MIME, executables, malformed files, path traversal and Office archive bombs.
- Document RAG sources have a prompt-injection/untrusted-data boundary and a citation validation path; no live prompt-injection escape was demonstrated by this audit.

## Confirmed security engineering gap

Security SAST (`.github/workflows/security-static.yml`) and vulnerability scanning (`dependency-audit.yml`) were only configured for PRs into `main`, while the **actual backend production branch** is `release/core-without-study-abroad-20261027` and the **actual frontend production branch** is `fix/center-empty-chat-composer-20261102`. Recent backend PRs therefore passed backend integration and resource benchmarks without these security jobs gating their exact heads. This PR extends both audits to the current release targets and adds dedicated frontend CSRF/XSS/security-header/relay regression tests.

The static scanner currently **blocks high-severity Python findings**, and the dependency audit covers pinned npm and Python requirements. These automated gates improve coverage but do not prove the absence of vulnerabilities.

## Remaining gates — not PASS

1. **Authenticated two-account penetration test:** owner/non-owner CRUD for document download, private memory, project, conversation, artifacts and cloud upload; verify revocation after logout/reset and Google login. Use disposable accounts, not real customer material.
2. **Dynamic XSS/injection and prompt-injection E2E:** exercise safe synthetic payloads in the isolated, authenticated staging environment; validate rendering, output encoding, citations, hidden data and no cross-tenant retrieval.
3. **File and object-store isolation E2E:** checksum, MIME/ZIP bombs, size caps, multi-part and upload lifecycle; verify one owner's object cannot be downloaded by another user, including signed URLs.
4. **DoS, brute-force and concurrency:** run only in disposable staging with explicit budgets. Never flood Render Free production.
5. **SSRF and browser automation:** keep execution disabled until independent network-isolated sandbox, DNS/egress tests, prompt-injection, approvals and audit acceptance.
6. **Dependency advisories and IaC/secrets management:** review current workflow results, scan dependency transitive graphs as appropriate, verify Render/Vercel/Railway permissions and MFA/rotation, and audit actual infrastructure policies without printing secret values.
7. **Backups/restore and release controls:** off-host encrypted database + object-store restore rehearsal; verify branch protections/required checks with repository admin authorization (GitHub App returned 403 to branch-protection GET).
8. **Privacy/performance:** assess browser/voice session retention, alerting, rate limits, response headers and cold-start operation; site availability on free tier is not an authentication compromise.

No blanket “fully secure” certification is justified without these independent acceptance steps.
