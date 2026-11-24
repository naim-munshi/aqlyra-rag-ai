import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/app/api/admin/users/[userId]/route.ts", import.meta.url),
  "utf8",
);

test("admin mutation bytes are limited during streaming", () => {
  assert.match(source, /readBoundedJson\(request, 2048\)/);
  assert.match(source, /RequestBodyTooLargeError/);
  assert.match(source, /status: 413/);
  assert.match(source, /private, no-store/);
  assert.doesNotMatch(source, /request\.text\(\)/);
  assert.doesNotMatch(source, /request\.json\(\)/);
  assert.doesNotMatch(source, /Buffer\.byteLength/);
});

test("admin account mutations still require ownership and origin checks", () => {
  assert.match(source, /hasTrustedRequestOrigin\(request\)/);
  assert.match(source, /status: 403/);
  assert.match(source, /getAccessToken/);
  assert.match(source, /status: 401/);
  assert.match(source, /confirmation !== "DELETE ACCOUNT"/);
  assert.match(source, /confirm_email/);
});
