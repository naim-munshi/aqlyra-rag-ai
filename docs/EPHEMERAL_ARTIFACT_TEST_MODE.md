# Disposable artifact test mode (temporary, owner-approved)

For a temporary evaluation of Aqlyra's existing DOCX, XLSX, PPTX, PDF and Markdown artifact creation and download on Render Free, set:

```text
EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED=true
```

This setting defaults to `false`, and changes **only artifact creation**. It does not enable document uploads, grant cross-account access, bypass authentication, weaken production security settings, or assert `LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED=true`.

**Important: all generated files and artifact metadata in this mode are disposable.** A Render restart, redeploy, or instance replacement can delete the files without warning; multi-instance consistency is not supported. Do not upload confidential documents or rely on this as a production file workspace. Users should download generated files immediately. The API readiness field reports `artifact_storage: "ephemeral_test_only"`, not `ready`.

## Test procedure

1. Deploy the reviewed change, then set the temporary flag in the existing Render service (do not set `APP_ENV=development`).
2. Confirm backend health/readiness (and the readiness indicator `ephemeral_test_only`).
3. Sign in normally; request a synthetic paragraph as a DOCX with no private source documents, and download it immediately.
4. Repeat for PDF/XLSX/PPTX/Markdown. Verify files open and no second user's artifact is readable.
5. Set `EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED=false` to disable new temporary writes. Existing temporary files may disappear without notice.
6. Before commercial or production use, replace with durable owner-scoped storage, backups/restore tests, content durability, download and delete lifecycle, and access-control acceptance.

This test mode is **not** a durable storage solution.