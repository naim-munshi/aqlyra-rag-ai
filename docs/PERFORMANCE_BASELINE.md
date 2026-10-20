# Staging performance baseline

Aqlyra's free-resource staging target is a single Ubuntu ARM64 VM with
2 OCPUs and 12 GB RAM. Use this bounded read-only probe only on a server
you control or are explicitly authorized to test.

This script **does not** test LLM/RAG generation speed, token throughput,
embedding providers, indexing, voice sessions or number of concurrent
AI users. It measures only unauthenticated HTTP latency/availability.

## Preconditions

1. Complete the [staging smoke test](STAGING.md) against the public
   HTTPS origin. Never probe while applying migrations, restoring
   the database, or performing other maintenance.
2. Confirm the host is free of sensitive production user data.
3. The probe does not send API keys, login credentials, POSTs or
   user content; it caps runs at **100 GET requests** and
   **4 concurrent clients**.

## Initial sample

```bash
python3 scripts/ops/staging_smoke.py \
  --base-url https://staging.example.com

python3 scripts/ops/performance_probe.py \
  --base-url https://staging.example.com \
  --path /api/health \
  --requests 40 --concurrency 2
```

Repeat at one and four concurrent requests:

```bash
python3 scripts/ops/performance_probe.py \
  --base-url https://staging.example.com \
  --requests 40 --concurrency 1

python3 scripts/ops/performance_probe.py \
  --base-url https://staging.example.com \
  --requests 40 --concurrency 4
```

It reports response-time p50/p95 (nearest-rank, milliseconds),
completed requests per wall-clock second and the number of failed
responses. HTTP errors, timeouts, oversized responses and a
cacheable health check make the probe fail.

For a **measured**, agreed p95 SLO, an optional flag makes it a
regression gate: `--max-p95-ms 2000`. That number is illustrative;
do not claim 2 seconds is an achieved target before measurement.

Record each test's timestamp, git SHA, OCI region, host size, p50/p95,
RPS, errors, and observed CPU/RAM/disk usage. Repeat at least three
times before drawing conclusions. Do not export private metrics or
user data into a public repository.

## AI workload readiness still required

Keep the existing manual tests for email verification, Google login,
document ingestion, cross-user isolation, citation/refusal grounding,
streaming, voice and recovery. Test actual authenticated RAG
latency and provider rate limits using staging-only accounts.
Model-provider operations may cost money even when the host is free.
Never infer a total-user or concurrent-user capacity from this
read-only HTTP probe.
