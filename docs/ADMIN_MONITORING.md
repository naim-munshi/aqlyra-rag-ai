# Aqlyra admin monitoring — scoped release

**Branch:** `release/core-without-study-abroad-20261027`; **PR:** #36.
This feature adds a protected operational dashboard without changing the
existing PostgreSQL/pgvector schema, embeddings, upload paths or README.
Study Abroad remains deferred.

## Where to open it

- URL after the **real** Aqlyra backend is deployed: `/admin`.
- Sign in with an **email-verified Aqlyra account** that has been added
  to the backend's private `ADMIN_USER_IDS` environment variable.
- The profile menu displays **Admin monitoring** only to an approved
  account; direct guesses to `/admin` are also verified server-side.
- This panel is **not live** on Vercel yet: Phase 2 cloud backend,
  persistence, Redis and private storage remain unprovisioned.

## Creating an admin safely

No default or hardcoded superuser, no email-name-based permissions,
no invitation privilege escalation:

1. Create and verify your regular Aqlyra account on trusted staging.
2. As that user, obtain your own immutable UUID from
   `GET /api/v1/users/me` (do not share access tokens publicly).
3. In the **private FastAPI backend** environment, set
   `ADMIN_USER_IDS=<that UUID>`. Multiple IDs, comma separated,
   up to five unique canonical UUIDs. Never store these as a public
   `NEXT_PUBLIC_*` frontend variable or commit them to GitHub.
4. Restart only the backend using its usual safe rollout.
   Remove the UUID to revoke admin access; invalidate auth sessions
   separately if a device is compromised.
5. HTTPS, 2-account access tests and review are required before
   showing real operational data.

**Fail-closed:** empty/missing or invalid admin allowlist denies access.
Admin endpoints first require a revocable session JWT and an active,
verified user. Another authenticated user receives HTTP 403; anonymous
users receive HTTP 401. The Next.js page redirects anonymous users and
returns 404 for non-admin users. Both the frontend and backend set
`no-store` for dashboard JSON.

## What the panel actually measures

| Display | Source | Definition |
| --- | --- | --- |
| Registered accounts, enabled accounts, verified accounts | PostgreSQL | Database totals; **enabled is not currently online** |
| Daily signups (7 UTC days) | PostgreSQL | Number of new accounts on each day |
| Documents and conversations | PostgreSQL | Aggregate metadata record counts |
| Request count, 4xx/5xx, mean latency, rate-limit hits | Existing in-memory FastAPI monitoring | **One backend process since last restart** |
| Most requested endpoints | Existing bounded route-template counters | API route templates and aggregate counts, no raw path/query |

**No claim of unique website visitors, session geography,
IP address tracking, individual chat activity, Vercel edge traffic or
multi-replica/daily API totals.** Existing Prometheus counters are
process-local. In serverless (Vercel Functions) these counters may
reset after each invocation and should not be used for business-wide
traffic totals. Use an approved privacy-preserving shared telemetry
backend or a Vercel Web Analytics integration for real site visitors
after Phase 2; require consent/retention and data-use review first.

The panel intentionally **never exposes user emails, IPs, device
fingerprints, private messages, documents, OAuth secrets, raw request
URLs or session tokens**.

## Acceptance and limitations

- [x] Protected server endpoints, fail-closed immutable owner-ID allowlist
- [x] Frontend session check and server-authorized Admin page
- [x] Request-count/latency/errors and database-based account aggregates
- [x] Auto-refresh every minute, avoids counting own dashboard polls
- [x] Tests for unauthorized users, unverified users, invalid admin IDs,
      response data safety and metrics boundaries
- [ ] Real staging backend, verified owner UUID, SMTP/Resend, Neon/
      PostgreSQL, secure uploaded objects, Redis and actual HTTPS E2E
- [ ] Cross-process **shared** analytics and unique visits (if required)
- [ ] Consent, retention, privacy review and off-host restore evidence
- [ ] Independent GitHub review, exact-head CI, approved release

GitHub `main` is protected. **No merge and no production rollout**
without approved review and existing release gates.
