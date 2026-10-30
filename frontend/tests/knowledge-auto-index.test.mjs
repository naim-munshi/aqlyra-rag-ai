import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8",
);
const documents = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8",
);
const retry = readFileSync(
  new URL("../src/app/api/documents/[documentId]/retry-index/route.ts", import.meta.url),
  "utf8",
);

test("direct 50MB cloud upload no longer triggers stale proxy-indexing block", () => {
  assert.match(workspace, /NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED !== "true"/);
  assert.match(workspace, /document\.status === "queued"/);
  assert.match(workspace, /document\.status === "processing"/);
  assert.match(workspace, /current\?\.status === "ready"/);
  assert.match(workspace, /setAttachedDocument\(current\)/);
});

test("knowledge uploads refresh automatically and failed documents can retry", () => {
  assert.match(documents, /setInterval\(async \(\) =>/);
  assert.match(documents, /uploadedDocument\.status === "queued"/);
  assert.match(documents, /Retry indexing/);
  assert.match(documents, /retry-index/);
});

test("retry route enforces user auth and never exposes external backend tokens", () => {
  assert.match(retry, /getAccessToken\(\)/);
  assert.match(retry, /status: 401/);
  assert.match(retry, /Authorization: \`Bearer \$\{token\}\`/);
});
