import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const cloud = readFileSync(new URL("../src/lib/api/cloud-upload.ts", import.meta.url), "utf8");
const converse = readFileSync(new URL("../src/components/chat/rag-workspace.tsx", import.meta.url), "utf8");
const documents = readFileSync(new URL("../src/components/documents/document-panel.tsx", import.meta.url), "utf8");
const prepare = readFileSync(new URL("../src/app/api/documents/cloud/prepare/route.ts", import.meta.url), "utf8");

test("max 50MiB client upload does not use a Vercel body-carrying function", () => {
  assert.match(cloud, /MAX_CLOUD_UPLOAD_BYTES = 50 \* 1024 \* 1024/);
  assert.match(cloud, /credentials: "omit"/);
  assert.match(cloud, /method: "PUT"/);
  assert.match(cloud, /https:/);
  assert.match(cloud, /aws\.neon\.tech/);
  assert.match(cloud, /\/api\/documents\/cloud\/prepare/);
  assert.match(cloud, /\/finalize/);
});

test("Converse and Documents use the same owner-scoped cloud uploader", () => {
  assert.match(converse, /NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED === "true"/);
  assert.match(converse, /await uploadViaPrivateCloud\(file\)/);
  assert.match(documents, /await uploadViaPrivateCloud\(file\)/);
  assert.match(converse, /NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED !== "true"/);
});

test("cloud manifest is still authenticated, small, and bounded", () => {
  assert.match(prepare, /getAccessToken\(\)/);
  assert.match(prepare, /readBoundedJson\(request, 4096\)/);
  assert.match(prepare, /Authorization: \`Bearer \$\{token\}\`/);
});

test("direct uploads keep explain-photo and pending-indexing status separate", () => {
  assert.match(converse, /setAttachedDocument\(document\)/);
  assert.match(converse, /AI indexing is not yet available/);
});
