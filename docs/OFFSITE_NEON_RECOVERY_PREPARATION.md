# Aqlyra — off-host database + cloud-object recovery preparation

**Status (11 November 2026): implemented and unit-testable, NOT OPERATING.** The Neon project refused automatic snapshot configuration with `HTTP 404 backup schedule creation is not enabled`, and the current manual snapshot (28 October) is retained. The software team must not delete this snapshot to free a quota slot. The separate GitHub workflow below is **manual opt-in** and cannot run until independent backup credentials, encryption recipient and an approved GitHub environment are configured.

## What the new export actually covers

1. PostgreSQL 18 custom-format `pg_dump` streamed through `age` encryption, with only ciphertext written to the ephemeral export runner.
2. Every existing `cloud_upload_intents` completed, un-deleted, owner+checksum+size-bound private object that is still linked to a Document. S3 object bytes are checked for exact SHA256 and streamed directly through an encrypted tar. Current read-only inventory: **25 bound objects / approximately 28 MB** (subject to change).
3. Two `.age` components uploaded to an **independent** offsite S3 bucket; `COMPLETE.json` with ciphertext SHA256 and sizes is published last. Unfinished exports have no COMPLETE marker.
4. Offline-only validator `scripts/ops/verify_offsite_bundle.py` checks archive hashes, decrypted PostgreSQL structure, private object count and SHA. The operator's **private age identity stays offline**, never in Neon, Render, GitHub secrets or chats.

Each run has a distinct random-suffixed export prefix and the Actions workflow serializes manual runs. The exporter does not take an atomic cross-service snapshot of Postgres + cloud objects, does not yet establish an RPO/RTO, and cannot automatically recover local ephemeral uploads. It refuses objects above 100 MB and collections above 2 GiB as a safety budget. Import into an isolated disposable database and independently owned test bucket remains an additional recovery acceptance gate.

## Configure once, without sharing secrets in chat

1. Create a separate private offsite S3 bucket with private ACL, blocked public access, object versioning/retention, cost alerts and an account-specific least-privilege writer restricted to `aqlyra/backup-v1/*`. It must not be the same Neon private source bucket.
2. Generate a modern `age` X25519 identity on a trusted **offline machine** with `age-keygen`; securely store the **private identity offline** and separately preserve one independent recovery copy. Put **only its public recipient** in GitHub environment variable `AQ_AGE_PUBLIC_RECIPIENT`.
3. In the GitHub repository, configure a protected Actions Environment named `offsite-backup`, restrict deployment to `release/core-without-study-abroad-20261027`, and require an independent reviewer. Do not enable a backup job for unreviewed fork/PR code.
4. Set environment variables `AQ_OFFSITE_BACKUP_ENABLED=yes`, `AQ_OFFSITE_BACKUP_CONFIRMED=offsite-v1`, `AQ_OFFSITE_BUCKET`, `AQ_PG18_IMAGE` (reviewed `postgres:18@sha256:<64-hex-digest>` for the correct runner architecture), `AQ_OFFSITE_AWS_REGION`, `AQ_NEON_S3_REGION`, optionally `AQ_OFFSITE_ENDPOINT`, and `AQ_AGE_PUBLIC_RECIPIENT`.
5. Set encrypted GitHub Environment **secrets**: `AQ_NEON_BACKUP_DATABASE_URL` (read-only backup DB role supporting `pg_dump`), `AQ_NEON_S3_ENDPOINT`, `AQ_NEON_S3_BUCKET`, `AQ_NEON_S3_ACCESS_KEY_ID`, `AQ_NEON_S3_SECRET_ACCESS_KEY`, `AQ_OFFSITE_AWS_ACCESS_KEY_ID`, and `AQ_OFFSITE_AWS_SECRET_ACCESS_KEY`.
6. Review `.github/workflows/offsite-neon-backup.yml` and `scripts/ops/offsite_neon_export.py` on the exact release SHA. Run the workflow **manually** only after reviewers approve. Confirm `AQLYRA_OFFSITE_ENCRYPTED_EXPORT=PASS` and inspect the independent S3 `COMPLETE.json` via a trusted operator.
7. Download the three objects (`postgres.dump.age`, `cloud-objects.tar.age`, `COMPLETE.json`) into a restricted scratch folder on a trusted restore machine. Keep the offline identity **outside** that folder. Set `AQ_OFFSITE_BUNDLE_DIRECTORY`, `AQ_OFFSITE_AGE_IDENTITY_PATH`, and the reviewed public `AQ_PG18_IMAGE` locally; run `python scripts/ops/verify_offsite_bundle.py`. It performs read-only verification and reports `LIVE_DB_RESTORE=NOT_ATTEMPTED`.
8. Restore **only into a disposable, isolated PostgreSQL 18 target and separate private object test bucket**. Compare Alembic revision, database/table counts, exact object sizes/SHA256 and owner-only retrieval. **Never point any restore command at the production DB or bucket.** Sign off the disaster-recovery test evidence and record total elapsed time before claiming recovery acceptance.

## Important GitHub scheduling limitation

GitHub `schedule` and newly added `workflow_dispatch` definitions require the workflow to be present on the **default branch**. Aqlyra's default `main` is protected, behind the backend release and has no independent approval on [PR #36](https://github.com/naim-munshi/aqlyra-rag-ai/pull/36). Therefore this workflow intentionally carries **no automatic schedule** and **must not be described as an active daily backup** until an independently reviewed, same-workflow migration to the protected default branch and backup verification actually occur. Avoid changing branch protection or creating provider credentials solely to make a report look green.

## Existing local acceptance

The existing [disposable local DB+upload restore CI run](https://github.com/naim-munshi/aqlyra-rag-ai/actions/runs/42764481022) passed with public/synthetic data. This cannot substitute for encrypted off-host Neon private-object restore and does not include the inaccessible legacy local PNG bytes.

**Failure policy:** A missing source, missing age recipient, unverified owner key, mismatched hash, unavailable backup provider, incorrect destination, or missing approval must fail without touching the real database or claiming success.
