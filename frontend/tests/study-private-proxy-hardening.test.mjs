import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/app/api/study-abroad/[...path]/route.ts", import.meta.url),
  "utf8",
);

test("Study Abroad private routes fail closed to CSRF and never use shared caching", () => {
  assert.match(source, /hasTrustedRequestOrigin\(request\)/);
  assert.match(source, /Cross-origin request denied/);
  assert.match(source, /export const dynamic = "force-dynamic"/);
  assert.match(source, /"Cache-Control": "private, no-store, max-age=0"/);
  assert.match(source, /"Vary": "Cookie"/);
  for (const status of [400, 401, 403, 413, 502, 503]) {
    assert.match(source, new RegExp("status: " + status + "[^}]*headers: privateHeaders"));
  }
  assert.match(source, /status: 204, headers: privateHeaders/);
});

test("Expired or unavailable auth cannot forward private requests", () => {
  assert.match(source, /try \{\s*token = await getAccessToken\(\);/);
  assert.match(source, /Session temporarily unavailable/);
  assert.match(source, /if \(!token\)/);
});

test("Invalid upstream JSON produces a 502, not a false-success 200", () => {
  assert.match(source, /if \(payload === null\)/);
  assert.match(source, /Invalid backend response/);
  assert.match(source, /status: 502, headers: privateHeaders/);
});
