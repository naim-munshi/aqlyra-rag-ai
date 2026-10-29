# Private Neon S3 diagnostic — isolated operator acceptance

## Purpose / boundaries

Aqlyra's Render backend now has a branch-scoped Neon storage credential and a
private `private-documents` bucket. Credentials alone do **not** prove the
bucket accepts signed S3 writes, or that processed RAG documents remain durable.

`backend/app/services/private_storage_probe.py` performs only a deliberately
isolated **synthetic** write → read → delete → absence-confirmation sequence in a
fresh, random `ops/aqlyra-storage-probes/<UUID>.bin` key. It never lists,
reads, modifies or deletes keys under `documents/` or `artifacts/`.
Its payload is small random bytes, not customer information.

This diagnostic works with `PRIVATE_OBJECT_STORAGE_ENABLED=false` and
`CLOUD_UPLOAD_PUBLIC_ENABLED=false`: it must **not** activate public uploads
or generated-artifact remote storage. A successful outcome proves only the
provider credentials/network can perform basic object operations at that moment.
It does **not** establish tenant isolation, browser presigning, uploads/finalize,
S3 retention, restarts, backup/restore, quota or secure garbage collection.

## Procedure

- Only the owner/operator, on an already-reviewed backend commit with passing CI,
  may explicitly set `AQLYRA_PRIVATE_STORAGE_PROBE_ON_BOOT=true` in the backend
  deployment's **private** environment. No application API or anonymous user
  can invoke this probe. A boot prints exactly `PRIVATE_S3_PROBE=PASS` or
  `PRIVATE_S3_PROBE=FAIL` without logging keys, endpoints, payloads or tokens.
- If the result is FAIL, **do not enable** `PRIVATE_OBJECT_STORAGE_ENABLED`,
  `ARTIFACT_REMOTE_STORAGE_ENABLED`, or `CLOUD_UPLOAD_PUBLIC_ENABLED`.
  Investigate provider IAM/endpoint restrictions in the secret manager; do not
  send access tokens into tickets or public logs.
- If PASS, immediately turn the boot probe OFF and repeat deployment health
  checks. Feature flags remain OFF pending separate owner/restart/tenant E2E.
- The helper cleans up the unique diagnostic object even if the read fails;
  deletion is additionally checked by `HeadObject`. If provider delete fails,
  this diagnostic reports FAIL. Only inspect/delete the unique operator
  diagnostic prefix after manual review; never run prefix-wide production
  cleanup or alter document/artifact prefixes.

## Real product acceptance still required

1. Authenticated private upload-intent → browser PUT → finalize → immutable
   server final key → process → verified pgvector/citation answer on the same
   release/schema.
2. Real Render restart/redeploy and independent worker read; existing local
   document recovery verified before any routing cutover.
3. Two verified test accounts: cross-tenant presign, document IDs, blob download,
   processing and deletion all denied.
4. Artifact five-format create/list/download/restart/delete, stable HMAC signing
   key, explicit quota / orphan checks.
5. Separately tested off-host Postgres backup and isolated restore. Neon
   no-compute recovery branches are not off-host backups.
6. Verify HTTPS domain/OTP/Google/reset/voice and HF inference credit in real
   browser and provider environments; CI pass alone cannot certify these.

Do not merge to `main` or mark full production launch COMPLETE until the
release owner approves all gates.
