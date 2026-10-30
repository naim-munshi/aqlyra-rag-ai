import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const route = readFileSync(
  new URL("../src/app/api/documents/upload/route.ts", import.meta.url), "utf8"
);
const workspace = readFileSync(
  new URL("../src/components/chat/rag-workspace.tsx", import.meta.url), "utf8"
);
const panel = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url), "utf8"
);

test("new upload feature stays OFF without the server-only opt-in", () => {
  assert.match(route, /process\.env\.AQLYRA_UPLOAD_PROXY_ENABLED === "true"/);
  assert.match(route, /"\/documents\/cloud\/proxy"/);
  assert.match(route, /"\/documents\/upload"/);
  assert.match(route, /getAccessToken\(\)/);
});

test("UI does not claim provider indexing succeeded after secure upload", () => {
  assert.match(panel, /NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED/);
  assert.match(panel, /File saved in private storage/);
  assert.match(workspace, /NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED/);
  assert.match(workspace, /AI indexing is not yet available/);
});

test("production frontend limits proxy mode to 3MB before forwarding", () => {
  if (route.includes("readBoundedBodyBytes")) {
    assert.match(route, /MAX_PROXY_FILE_BYTES = 3 \* 1024 \* 1024/);
    assert.match(route, /MAX_PROXY_FILE_BYTES \+ 128 \* 1024/);
    assert.match(route, /readBoundedBodyBytes\(request, maxBodyBytes\)/);
  }
});
