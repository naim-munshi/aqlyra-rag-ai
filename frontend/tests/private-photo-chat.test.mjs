import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url),
  "utf8",
);
const uploadRoute = readFileSync(
  new URL("../src/app/api/documents/upload/route.ts", import.meta.url),
  "utf8",
);

test("chat picker accepts only supported image and file types", () => {
  assert.match(workspace, /accept="\.pdf,\.docx,\.xlsx,\.pptx,\.txt,\.md,\.csv,\.png,\.jpg,\.jpeg,\.webp"/);
  assert.match(workspace, /URL\.createObjectURL\(file\)/);
});

test("direct verified cloud photos are attachable without embedding processing", () => {
  assert.match(workspace, /document\.status === "uploaded"/);
  assert.match(workspace, /\["image\/png", "image\/jpeg", "image\/webp"\]\.includes\(document\.content_type\)/);
  assert.match(workspace, /setAttachedDocument\(document\)/);
  assert.match(workspace, /AI indexing is separate/);
});

test("front and secure server proxy enforce the same 3 MiB upload cap", () => {
  assert.match(workspace, /file\.size > 3 \* 1024 \* 1024/);
  assert.match(workspace, /Choose a file or image of 3 MB or less/);
  assert.match(uploadRoute, /MAX_PROXY_FILE_BYTES = 3 \* 1024 \* 1024/);
  assert.match(uploadRoute, /"\/documents\/cloud\/proxy"/);
});

test("file picker upload still requires authenticated server-side session", () => {
  assert.match(uploadRoute, /getAccessToken\(\)/);
  assert.match(uploadRoute, /status: 401/);
});
