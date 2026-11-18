# Disposable artifact test mode (temporary, owner-approved)

For a temporary evaluation of DOCX, XLSX, PPTX, PDF and Markdown artifact creation on Render Free **only when private object storage is not configured**, set:

```text
EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED=true
```

This setting defaults to `false`, and changes **only artifact creation**. It does not enable document uploads, grant cross-account access, bypass authentication, weaken production security settings, or assert `LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED=true`.

When the complete private Neon object storage configuration is enabled, Aqlyra now uses that private bucket for new artifacts instead of this local test mode. Readiness reports `private_object_storage_configured` for that configuration, but a successful live provider probe and restore rehearsal are still required.

**Important: all generated files and artifact metadata in this local test mode are disposable.** A Render restart, redeploy, or instance replacement can delete the files without warning; multi-instance consistency is not supported. Do not upload confidential documents or rely on this as a production file workspace. Users should download generated files immediately. The API readiness field reports `artifact_storage: "ephemeral_test_only"`, not `ready`.

## Test procedure

1. Deploy the reviewed change, then set the temporary flag in the existing Render service (do not set `APP_ENV=development`).
2. Confirm backend health/readiness (and the readiness indicator `ephemeral_test_only`).
3. Sign in normally; request a synthetic paragraph as a DOCX with no private source documents, and download it immediately.
4. Repeat for PDF/XLSX/PPTX/Markdown. Verify files open and no second user's artifact is readable.
5. Set `EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED=false` to disable new temporary writes. Existing temporary files may disappear without notice.
6. Do not use local ephemeral mode for commercial or production use. The private object-storage path must pass an owner-approved synthetic provider write/read/delete probe, authenticated two-account isolation tests, and an encrypted offsite restore rehearsal before production acceptance.

This test mode is **not** a durable storage solution.