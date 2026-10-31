# Private AI artifact storage: rollout and acceptance

**Status (31 October 2026):** implementation candidate in [PR #82](https://github.com/naim-munshi/aqlyra-rag-ai/pull/82). **Not an accepted production feature.** The existing Render Core backend and Vercel frontend are separate deployed commits. Never infer deployment or data durability from CI alone.

## Safety boundaries

- This is an **opt-in S3-compatible, owner-scoped** artifact store for generated Markdown, PDF, DOCX, XLSX and PPTX, not public document upload storage.
- There is **no automatic import or dual-read** of earlier `UPLOAD_DIR/artifact-workspace` files. Enabling remote storage changes the active artifact read/list/write path. **Before switching, inventory and preserve any existing local artifacts, plan and verify a reversible migration, and confirm the owner approves the visibility change.** Do not erase legacy files.
- Never point staging to the production user database, object bucket, local upload volume, or HMAC key. Do not deploy this candidate directly to the current Render Core merely to test it.
- Metadata is signed with a dedicated, stable secret. Rotating or losing that secret makes previously signed metadata unreadable. Protect it in a secrets manager and include key recovery in the documented encrypted backup procedure. Never commit, print or share its value.
- Enabling the setting alone is not acceptance: account isolation, actual rendered files, deletion, restart durability, real provider output, storage outage behaviour and independent restore all need separate evidence.
- The storage canary uses only generated synthetic UUID namespaces. It does not exercise real user sessions, restart durability or backup restoration. A failing cleanup must be investigated before any live rollout; do not bulk-delete keys.

## Production-like isolated staging configuration

Configure in the private host environment, **not** in git, chat, CI logs or a checked-in `.env`:

| Variable | Purpose |
| --- | --- |
| `PRIVATE_OBJECT_STORAGE_ENABLED=true` | Use the already reviewed private Neon S3 client |
| `AWS_ENDPOINT_URL_S3`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `OBJECT_STORAGE_BUCKET` | Separate staging endpoint, region, credentials and private bucket |
| `ARTIFACT_REMOTE_STORAGE_ENABLED=true` | Opt in to remote reads/writes, without local-disk fallback |
| `ARTIFACT_METADATA_HMAC_KEY` | Distinct stable secret, at least 32 characters; strong random key recommended |
| `ARTIFACT_STORAGE_CANARY_ON_STARTUP=true` | **Temporary staging-only** five-format synthetic write/read/isolation/delete smoke; default **false** |

Keep `ARTIFACT_REMOTE_STORAGE_ENABLED=false` and `ARTIFACT_STORAGE_CANARY_ON_STARTUP=false` in the current production release until the full gate is accepted. Verify the private bucket has no public ACLs, bucket policy or externally accessible presigned reads.

## Acceptance checklist — record sanitized PASS/FAIL per exact commit

1. **Release identity:** record separate GitHub HEAD, backend Render deploy commit, frontend Vercel deploy commit, environments and deployment statuses. Confirm the intended code actually includes this implementation. Require all exact-head backend/PostgreSQL 16+18, static security, dependency, frontend, Docker, ARM64 and documentation checks.
2. **Recovery first:** perform and independently verify encrypted off-host PostgreSQL, private objects, and legacy local artifacts backup; restore into **separate disposable infrastructure**. Capture object count/checksum reconciliation, RPO/RTO and an approved rollback snapshot. Do not test restore against live users.
3. **Synthetic storage:** in isolated staging only, run the opt-in startup canary and verify all five file formats, owner-scoped read/download/delete and exact-ID cleanup. The log must show `artifact_storage_canary status=PASS` and `cleanup=PASS`. A synthetic test is not authenticated E2E.
4. **Two-account live flows:** create two independent staging accounts. Through the actual UI and authenticated API, create, list, download and delete each of the five formats under account A; ensure account B gets no metadata and cannot download/delete any A ID. Check session expiration and revocation. Verify headers do not cache or inline-render private content.
5. **AI/document evidence:** run genuine provider-backed in-chat generation with and without selected private documents, explicit source-consent enforcement, grounded citations, and refusal on unsupported evidence. Keep the demo identified as **scripted** until these are verified.
6. **Durability:** restart and redeploy both API workers and check that artifacts and editable Markdown persist across new processes. Confirm a second instance obeys the shared PostgreSQL advisory-lock quota. Test configured storage outage, 503 responses and **no** fallback to ephemeral disk.
7. **Failure handling:** simulate rejected S3 writes, missing objects, corrupt bytes/metadata, metadata-signature mismatch and failed deletion in disposable staging. Require sanitized API errors and inventory reconciliation. Investigate orphan objects without scanning/deleting unrelated owners.
8. **Legacy handoff:** inventory any pre-existing `UPLOAD_DIR/artifact-workspace` data and reconcile every user-owned file before enabling the remote-only route. Preserve original files until a verified reversible migration and independent sign-off.
9. **Release approval:** obtain independent review and owner approval, then promote only the accepted deployment commit with rollback and monitoring. Disable startup canaries after acceptance. No `main` merge, production migration or deploy is authorized by this guide.

## Failure and rollback

On any FAIL: stop rollout and do not overwrite existing data. If reverting the remote flag after new artifacts were created, **back up and reconcile remote objects first**: switching back to local hides those artifacts until migrated. Keep both stores preserved, report only sanitized counts, and use a reviewed recovery plan. A successful local or mocked test is never a substitute for a real off-host restore or end-user acceptance.

Related: [AI Artifact Workspace](AI_ARTIFACT_WORKSPACE.md), [Production status](PRODUCTION_STATUS_2026-10-31.md), [Release acceptance](RELEASE_ACCEPTANCE.md).
