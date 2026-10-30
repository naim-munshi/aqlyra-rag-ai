import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const panel = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8"
);
const route = readFileSync(
  new URL("../src/app/api/documents/[documentId]/content/route.ts", import.meta.url),
  "utf8"
);

test("uploaded files can be downloaded without waiting for RAG indexing", () => {
  assert.match(panel, /"uploaded", "ready", "failed"/);
  assert.match(panel, /Download original/);
  assert.match(panel, /encodeURIComponent\(document\.id\)/);
  assert.match(panel, /noopener noreferrer/);
});

test("download uses authenticated server-authorized private URL, not public bucket", () => {
  assert.match(route, /getAccessToken\(\)/);
  assert.match(route, /status: 401/);
  assert.match(route, /response\.status === 307/);
  assert.match(route, /\.aws\.neon\.tech/);
  assert.match(route, /Cache-Control/);
  assert.match(route, /Referrer-Policy/);
});
