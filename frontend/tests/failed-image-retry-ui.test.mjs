import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const panel = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8",
);
const retry = readFileSync(
  new URL("../src/app/api/documents/[documentId]/retry-index/route.ts", import.meta.url),
  "utf8",
);

test("previously failed PDF and image OCR sources share owner retry button", () => {
  assert.match(panel, /document\.status === "failed" && \(/);
  assert.doesNotMatch(
    panel,
    /document\.status === "failed" &&\s*!\["\.png"/,
  );
  assert.match(panel, /void retryIndex\(document\.id\)/);
  assert.match(panel, /Retry indexing/);
});

test("retry preserves backend source-unavailable 409 for owner UI", () => {
  assert.match(panel, /getErrorMessage\(payload as ApiError/);
  assert.match(retry, /getAccessToken\(\)/);
  assert.match(retry, /status: 401/);
  assert.match(retry, /result\.status/);
  assert.doesNotMatch(retry, /console\.(log|error)\(/);
});
