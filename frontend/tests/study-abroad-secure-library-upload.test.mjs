import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
const source = readFileSync(
  new URL("../src/components/study-abroad/study-abroad-workspace.tsx", import.meta.url), "utf8",
);

test("Study Abroad reuses the secure 50MiB direct grant instead of proxying large bytes", () => {
  assert.match(source, /uploadViaPrivateCloud\(file\)/);
  assert.match(source, /NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED === "true"/);
  assert.match(source, /cloudEnabled \? 50 \* 1024 \* 1024 : 3 \* 1024 \* 1024/);
  assert.match(source, /Secure cloud upload \(up to 50 MiB when enabled\)/);
});

test("queued or unindexed files are saved without falsely claiming they are attached", () => {
  assert.match(source, /if \(saved\.status === "ready"\)/);
  assert.match(source, /indexing is not complete/);
  assert.match(source, /saved\.status === "uploaded"/);
  assert.match(source, /refreshLibraryDocs\(\)/);
  assert.match(source, /File saved securely in My Documents/);
});

test("an existing owner-scoped ready file can be linked without uploading again", () => {
  assert.match(source, /fetch\("\/api\/documents"/);
  assert.match(source, /Attach from My Documents \(no re-upload\)/);
  assert.match(source, /Attach ready file/);
  assert.match(source, /document_id: documentId, checklist_key: uploadKey/);
  assert.match(source, /status !== "ready"/);
  assert.match(source, /Retry indexing/);
});
