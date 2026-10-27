# Aqlyra Phase 2 — Railway staging infrastructure (safe, not deployed)

**Repository:** `naim-munshi/aqlyra-rag-ai` only. **Scope:** core release
[PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36),
`release/core-without-study-abroad-20261027` at pinned SHA
`b5fa5666790b711d081f250bf1c44c8c6c22b8d8`. Keep the README,
pgvector schema, uploaded files, embedding dimension and RAG ingestion
architecture intact. Study Abroad is deferred, not available in staging.

## Verified platform inventory, 2026-10-27 JST

- Railway project: `Aqlyra-Staging`,
  `2bfca66f-8c1d-487f-9092-f93e54171b9c`.
- Environment: `staging`,
  `fe9fb667-22fa-445b-aa90-73b34fb6fac9`.
- Existing `aqlyra-backend`: staged GitHub source pinned to the core SHA,
  Docker root `/backend`, health `/api/v1/health`, one Oregon replica.
- Existing `aqlyra-frontend`: staged GitHub source pinned to core SHA,
  Docker root `/frontend`, health `/`, one Oregon replica.
- Existing `aqlyra-postgres-pgvector`: staged
  `pgvector/pgvector:pg16` source.
- Staged persistent volumes (NOT provisioned):
  `aqlyra-staging-pgdata` at `/var/lib/postgresql/data` (500 MB) and
  `aqlyra-staging-uploads` at `/app/uploads` (500 MB).
- Existing voice/alert services are **not provisioned**; do not enable
  until voice worker and monitoring dependencies are accepted.
- The frontend's staged `BACKEND_API_URL` references the backend
  private Railway DNS at port 8000, not a public backend URL.
- Backend's staged flags reject deterministic production AI, disable
  Browser Agent, and require verified registration/grounded RAG.
- **No live deployments and no public Railway domain verified.**
- Creating a new `aqlyra-redis` service returned
  `Free plan resource provision limit exceeded`; no Redis service was
  created. There are also no verified usable provider/SMTP/OAuth secrets.
  **This is a blocking hosting/quota issue.**

All staged resources and settings are drafts only. Do not click
`Deploy`, `Accept Changes`, or create a public domain until the quota,
secrets, and privacy requirements below are satisfied. No resources or
user files were destroyed or migrated.

## Non-negotiable storage constraints

The existing Docker Compose architecture uses distinct persistent
`postgres_data` and `uploads_data` volumes. A live Railway backend
without `/app/uploads` persistence will silently lose private files on
redeployment. A live PostgreSQL instance without
`/var/lib/postgresql/data` persistence will lose account, document,
chunk, pgvector index and memory state on redeployment.

Railway's published Free limits include **one volume per project**
and a 0.5 GB size limit. Although two volumes could be **staged**, do
not assume both can be applied successfully on that plan. With the
additional service provision quota error, full-stack real staging is
**BLOCKED** on currently accessible Railway resources. Do not work
around these restrictions by removing PostgreSQL or upload
persistence, exposing a database port, or combining unrelated database
and application processes into a single container.

The backend and voice worker both mount the same local upload volume
in Docker Compose, whereas Railway volumes are attached to one
service. Before running the independent voice worker on Railway,
implement and test a secure shared object-storage abstraction, or keep
voice-worker deployment disabled. Voice is not a reason to compromise
core RAG persistence.

## Host decision (no automatic plan upgrade)

1. **Railway upgrade / adequate quota:** Owner must explicitly approve
   any paid plan and estimate before provisioning more resources.
   Verify the plan supports at least 4 services (pgvector, Redis,
   backend, frontend) and 2 separately mounted volumes in the project.
2. **Free-first alternative:** Use an eligible OCI Always Free ARM64 VM
   in the approved home region when the OCI tenancy is actually
   available. Follow `docs/ORACLE_ALWAYS_FREE.md` and
   `docs/STAGING.md`. Its single-host Compose profile preserves the
   *existing* backend/voice shared uploads volume and database
   boundaries without Railway volume restrictions. Account approval,
   capacity and billing eligibility are not guaranteed.
3. A disposable CI-only ARM64 stack already passes in GitHub Actions;
   it is not a persistent external HTTPS staging server.

## Operator-only staging readiness

Before applying the Railway draft:

1. Keep all secrets in Railway's sealed/private variables, never
   README, GitHub comments, or chat. Create independent staging-only
   `SECRET_KEY` (32+ random chars), PostgreSQL password, SMTP
   credentials, Google OAuth client, Groq/OpenAI key, Hugging Face
   token and LiveKit secrets if voice is enabled. Do not copy
   credentials from production.
2. The official pgvector image needs `POSTGRES_USER`,
   `POSTGRES_PASSWORD`, `POSTGRES_DB` and the PostgreSQL persistent
   volume. Keep TCP 5432 private and use an URL-encoded password in
   `DATABASE_URL` for the FastAPI backend.
3. Provide a Redis service reachable privately at port 6379; keep
   Redis TCP/private DNS inaccessible to public internet. Enable Redis
   rate limiting with `RATE_LIMIT_ENABLED=true`.
4. Configure `APP_ENV=production`, `DEBUG=false`,
   `BROWSER_AGENT_ENABLED=false`, exact HTTPS
   `CORS_ORIGINS`, real Hugging Face semantic embeddings with
   `EMBEDDING_DIMENSION=384`, real configured LLM and
   `RAG_GROUNDING_VERIFIER_ENABLED=true`. No test/deterministic
   provider fallback.
5. The frontend Docker image embeds
   `NEXT_PUBLIC_GOOGLE_CLIENT_ID` during build, **not only runtime**.
   Rebuild with the authorized staging Client ID. Its
   `BACKEND_API_URL` must use private Railway networking:
   `http://${{aqlyra-backend.RAILWAY_PRIVATE_DOMAIN}}:8000/api/v1`.
   Expose only frontend `:3000` through Railway's HTTPS domain.
6. Keep source pinned to a reviewed exact SHA. Confirm the database
   migration `f18a3c42e917` using **synthetic restored staging data**.
   Do not apply the deferred Study Abroad revision
   `d4ec2f9b7860`.
7. After quota/secrets approvals and intentional staging deployment,
   wait for **terminal SUCCESS** for every service. Verify persistent
   volumes, private network, HTTPS, login page and authorization,
   health endpoint, OpenAPI isolation, cross-user RAG, and backup
   restore. Then run:
   ```bash
   python3 scripts/ops/staging_smoke.py --base-url https://YOUR_STAGING_DOMAIN
   ```
   Add provider-backed tests and evidence to Issue #34. The
   dedicated Caddy proxy is used by the OCI/Compose deployment, but
   on Railway its managed HTTPS ingress replaces Caddy; only
   frontend is exposed.

## Read-only Railway structural gate

The offline read-only gate checks a sanitized inventory of
`describe-environment` plus `describe-service` results. Include
`project`, `environment`, `staged`, `services` with each
service's `config`, `state`, `volumes`, `domains`,
`tcpProxies`, `variableNames`, and `latestDeployment`.
**Do not copy real variable values, tokens or registry secrets.**

```bash
python3 -m unittest discover -s scripts/ops -p 'test_*.py' -v
python3 scripts/ops/railway_staging_gate.py \
  /path/to/sanitized-railway-inventory.json \
  --commit b5fa5666790b711d081f250bf1c44c8c6c22b8d8 --json
```

A structural PASS still does not prove TLS, provider-backed RAG,
security, data backup or Phase 2 acceptance. The currently verified
staged-only Railway project **must fail** this gate until capacity,
creds, deploy and runtime verification are complete.

## Remaining owner decisions

- Confirm Railway paid-quota vs a successfully provisioned OCI Always
  Free VM before incurring compute/volume costs.
- Provide a real staging-only domain if using custom HTTPS origin;
  a Railway-generated `*.up.railway.app` staging subdomain is also
  possible, but must pass real TLS and headers checks.
- Arrange SMTP, Google OAuth, Groq/HF providers and privacy consent.
- Do not merge PR #36 until independent GitHub review and required
  release acceptance evidence. **Staging deploy does not authorize
  main merge or production deployment.**
