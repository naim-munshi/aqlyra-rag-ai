# Security and Testing

## What is covered

Aqlyra includes application-level security controls for authentication, user isolation, uploads, RAG behavior, rate limiting, logging, and production configuration.

The test suite also checks a number of failure and adversarial cases.

## Authentication and ownership

Email syntax alone is not treated as proof of mailbox ownership.
New password accounts remain unverified until a one-time code is
accepted. Verification codes:

- contain six digits and expire after ten minutes;
- are stored as keyed HMAC digests, never as plaintext;
- stop working after five incorrect attempts or after use;
- have resend cooldown and IP rate-limit protection;
- are bound to a short-lived signed verification ticket stored in an
  HttpOnly, SameSite cookie by the frontend session layer.

A second unauthenticated registration for an existing unverified email is
rejected instead of allowing its password or username to be overwritten.
The original verification challenge remains bound to the pending account.
This avoids an account pre-hijack race, but a mailbox-proof claim/recovery
flow for addresses that were registered by someone else is still a release
follow-up; do not ask users to retry with a different password as a workaround.

Google credentials are verified on the backend for signature,
audience, issuer, subject, and verified email before an Aqlyra session
is issued. A Google account can safely reclaim a matching unverified
email because the pending password is invalidated during linking.

Protected data is always read in the context of the authenticated user.

Ownership checks cover:

- documents;
- document content;
- conversations;
- messages;
- memory;
- Knowledge document scopes.

The backend does not treat a client-supplied user ID as proof of ownership.

## Cross-user access tests

The tests include cases where one user tries to access another user's:

- document;
- conversation;
- memory;
- document scope.

They also cover random IDs, missing authentication, and invalid scope combinations.

## Upload handling

Upload checks include:

- allowed extensions;
- size limits;
- filename sanitization;
- long filenames;
- corrupt inputs;
- parser failures.

The long-filename regression tests are important because filename sanitization must not remove a valid extension.

Office archives are bounded by entry count, expanded size, and compression
ratio to mitigate decompression bombs. Newly uploaded document files receive
owner-only `0600` permissions on Unix. The proxy rejects requests exceeding
32 MB; the application applies its own 25 MiB file limit.

## RAG safety

Knowledge mode checks both citation syntax and evidence support.

The tests cover:

- malformed citations;
- unknown source IDs;
- missing citations;
- citation laundering;
- unsupported claims;
- failed grounding checks;
- repair/refusal behavior.

A correct-looking `[S1]` label is not accepted if `[S1]` does not support the claim.

## Rate limiting

Redis-backed rate limits protect expensive and authentication-sensitive endpoints.

That includes areas such as:

- registration;
- login;
- repeated failed login attempts;
- email verification and resend requests;
- uploads;
- document processing;
- RAG answers;
- normal chat generation;
- voice sessions;
- retrieval searches and embedding rebuild requests.

Rate-limit responses use `429` and include `Retry-After`.

If Redis is required for the operation and unavailable, the protected route fails closed.

## Native ARM64 and reverse-proxy integration checks

The dedicated ARM64 workflow builds actual production Dockerfiles on
native ARM64 Linux runners, then starts the existing Caddy/Next.js/API/
PostgreSQL/Redis stack with **local-only** deterministic test settings.
A malicious cross-origin login request must receive HTTP 403 through
the real reverse proxy; the smoke check also expects anonymous routes
to return HTTP 401 and private metrics to remain inaccessible.

The CI rehearsal also verifies that an actual backup and restore cycle
recovers synthetic PostgreSQL and upload markers after they have been
changed. This is isolated from real user data and is **not** evidence
of recovery from an off-host encrypted production snapshot.

It cannot replace live HTTPS/SMTP/Google/LiveKit, real provider or
cross-account authenticated staging tests. Those tests must be
recorded against the eventual deployed Singapore VM.

## Deployment network and persistence contract

A deployment check consumes the canonical Compose production profile and
rejects configurations that accidentally expose PostgreSQL, FastAPI, Redis,
the frontend or workers to public host ports; grant app containers extra
Linux capabilities; enable privileged or host-network modes; or remove
persistent database/upload volumes. It also confirms that backend and
voice-worker share the same uploads volume.

The OCI host preflight and GitHub deployment CI share this check and
run negative-path unit tests. This protects the intended single-host
reverse-proxy topology but **does not** verify a live OCI security list,
SSH firewall, remote TLS, or Kubernetes/network-layer controls.

## Production configuration checks

The production configuration rejects unsafe settings such as:

- debug mode;
- wildcard or localhost CORS;
- weak application secrets;
- weak/default database credentials;
- disabled rate limiting;
- deterministic production LLM or embedding configuration;
- disabled grounding verification.

Production API docs/OpenAPI are disabled. Next.js also checks trusted
origin / browser fetch provenance for unsafe `/api/*` requests to reduce
cross-site request forgery. Browser sessions use HttpOnly cookies that are
Secure in production. FastAPI applies independent JWT and ownership checks.
A successful origin check is not an authorization grant.

The backend, voice worker, and frontend run under non-root users, with
Linux capabilities dropped and privilege escalation disabled for application
containers. Deployments upgrading from root-run containers must first verify
ownership of persisted upload files.

## Logging

Production logs use structured JSON.

The logging path avoids intentionally recording request bodies or credentials.

Sensitive values such as tokens, secrets, and emails are redacted where they can appear in operational events.

Unhandled errors return a generic response instead of exposing internal details.

## Monitoring and alerting

Metrics use bounded labels instead of raw document or conversation IDs.

The alert worker is tested for:

- firing;
- duplicate suppression;
- recovery;
- resolved events;
- secret-free payloads.

## Test suite

The full integration release candidate has **451 passing backend tests
with one warning** on the reviewed GitHub branch
(`integration/security-release-candidate-20261026`, verified CI head
`11597ee9f422a6a72e8dccb1035e1d4fc128dba6` before final UI/help
fixes). This is automated regression evidence, not live production proof.
Use the latest GitHub Actions run on the actual release SHA before approval.
The final application requires real-provider, staging, privacy and recovery
acceptance in addition to passing tests.

Coverage includes:

```text
authentication
tenant isolation
document ingestion
OCR
chunking
embeddings
dense retrieval
lexical retrieval
hybrid retrieval
RRF
retrieval evaluation
RAG context building
citation validation
semantic grounding adversarial cases
provider failures
conversation streaming
memory
voice sessions
production configuration
rate limiting
observability
monitoring
Redis readiness
alerting
```

## Test database

Backend tests use a separate PostgreSQL database:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aqlyra_rag_ai_test
```

The test suite must not be pointed at the normal development database because some fixtures recreate database state.

## Failure cases covered

Examples include:

- cross-user IDOR attempts;
- malformed uploads;
- corrupt files;
- long filenames;
- citation laundering;
- grounding failures;
- provider 429s;
- provider timeouts;
- provider network errors;
- Redis outage;
- alert firing and recovery;
- backup verification.

## Dependency vulnerability audit

The dedicated Dependency Security Audit workflow checks Python packages
and the production npm dependency graph on dependency changes and weekly.
Python pinning is audited for both the API and voice worker. The frontend
production dependency gate uses `npm audit --omit=dev --audit-level=high`.

The full frontend dependency graph is checked separately and reported
as non-blocking because some build-time development tooling pulls the
unpatched `braces` package (GHSA-vfj7-8cjw-p6xm, no fixed version as
of 2026-10-12). This exception does **not** apply to runtime packages;
any critical/high production advisory blocks the security workflow.
The full audit result stays visible in GitHub Actions, and the team
must reassess this exception after upstream publishes a patched version
or if an affected package enters the release runtime image.

GitHub Actions jobs use pinned action commit SHAs. Image builds, non-root
runtime identity checks, fresh-volume PostgreSQL/Redis/backend startup,
database migrations, and readiness checks are in deployment CI.
Container operating-system vulnerability scanning, real staging E2E tests,
off-host recovery drills, and `main` branch protection are still release
work, not completed validations.

The earlier Next.js runtime advisories were addressed by upgrading to
16.4.0 and generating a fresh npm lockfile. JWT handling has moved to
PyJWT with explicit allowed algorithm verification and regression tests.
