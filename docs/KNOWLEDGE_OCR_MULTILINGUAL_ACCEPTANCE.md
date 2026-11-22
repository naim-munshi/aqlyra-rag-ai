# Aqlyra Knowledge K3 — Scanned PDF and multilingual fallback

## Bounded scanned PDF OCR

- Existing private owner-verified Neon S3 files remain unchanged; only temporary
  local raster pages are used during indexing, and are deleted afterward.
- `KNOWLEDGE_PDF_OCR_ENABLED=false` is the default; turn it on only after
  production Docker `KNOWLEDGE_PDF_OCR_PROBE=PASS`.
- English, Japanese and Bengali installed Tesseract packs are required.
  Poppler `pdftoppm` is installed in the runtime Docker image.
- Only sparsely extracted PDF pages are rasterized, one at a time, max 2200px
  edge, max 9 megapixels and 20 MB raster output, with separate tool timeouts.
- `KNOWLEDGE_PDF_OCR_MAX_PAGES=20` limits OCR pages, not total text PDF
  pages. Scan-heavy PDFs beyond this limit fail as `failed` rather than
  reporting false `ready`.
- Original filename, document owner, `Page N` source label and per-page
  retrieval citations are preserved.
- Empty/unreadable scans never become searchable `ready` documents.

## Multilingual search under Hugging Face quota exhaustion

- Postgres full-text search is unchanged for English. When no FTS matches,
  Japanese/Kanji and Bengali queries use a **bounded** Unicode substring
  fallback with the same PostgreSQL owner, ready-state and document-id
  security filters.
- This is **lexical-only**, not cross-language semantic retrieval. The original
  text/citations are real, but paraphrases and translation may still fail.
  Vector/hybrid quality depends on restored embedding provider capacity.
- No new indexes, tables, database schema modifications or external search
  exposure are required in this beta.

## Readiness and limits

Use the one-shot `AQLYRA_KNOWLEDGE_OCR_PROBE_ON_BOOT=true` in production
with `KNOWLEDGE_PDF_OCR_ENABLED=true`. Inspect sanitized
`KNOWLEDGE_PDF_OCR_PROBE=PASS/FAIL` and turn the probe back off afterward.

Automated GitHub integration tests prove parsing, status, owner isolation,
UTF-8 retrieval and simulated OCR limits. A real signed-in user's
PDF → Queued → Processing → Ready → cited-answer, restart persistence,
PDF >20 pages / 50MiB transfer, and a second account's access denial must
still be tested on the public production website before marking full
user acceptance PASS.

Off-platform recoverable database/object backups and true live E2E remain
separate gates. Never fabricate completion from CI alone.
