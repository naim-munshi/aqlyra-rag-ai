import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const route = readFileSync(
  new URL("../src/app/api/documents/cloud/recover/route.ts", import.meta.url),
  "utf8"
);
const panel = readFileSync(
  new URL("../src/components/documents/document-panel.tsx", import.meta.url),
  "utf8"
);

test("pending upload recovery proxy always checks session and avoids cached secrets", () => {
  assert.match(route, /getAccessToken\(\)/);
  assert.match(route, /status: 401/);
  assert.match(route, /backendUrl\("\/documents\/cloud\/recover"\)/);
  assert.match(route, /cache: "no-store"/);
  assert.match(route, /Authorization: `Bearer \$\{token\}`/);
});

test("recovery action is explicit and only shown with private upload beta", () => {
  assert.match(panel, /NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED === "true"/);
  assert.match(panel, /Recover unfinished private file uploads/);
  assert.match(panel, /method: "POST", credentials: "same-origin"/);
  assert.match(panel, /setRecoveryNotice/);
  assert.match(panel, /Some pending files could not be verified/);
});
