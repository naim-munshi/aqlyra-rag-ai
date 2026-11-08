import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function source(relative) {
  return readFileSync(new URL("../src/" + relative, import.meta.url), "utf8");
}

const google = source("app/api/auth/google/route.ts");
const password = source("app/api/auth/login/route.ts");
const complete = source("lib/auth/complete-authentication.ts");

test("both login proxies bound backend requests and preserve no-store", () => {
  for (const [name, text] of [["google", google], ["password", password]]) {
    assert.match(text, /AbortSignal\.timeout\(45_000\)/, name);
    assert.match(text, /cache: "no-store"/, name);
    assert.match(text, /error\.name === "TimeoutError"/, name);
    assert.match(text, /status: 503/, name);
    assert.match(text, /"Retry-After": "5"/, name);
    assert.match(text, /"Cache-Control": "private, no-store"/, name);
    assert.match(text, /status: 502/, name);
    assert.doesNotMatch(text, /console\.(log|error)\(.*(password|credential)/);
  }
});

test("legacy profile fallback is bounded and tokens stay server-only", () => {
  assert.match(complete, /AbortSignal\.timeout\(15_000\)/);
  assert.match(complete, /cache: "no-store"/);
  assert.match(complete, /setAccessToken\(/);
  assert.match(complete, /setRefreshToken\(/);
  assert.match(complete, /clearRefreshToken\(/);
  assert.match(complete, /"Cache-Control": "private, no-store"/);
  assert.doesNotMatch(complete, /return NextResponse\.json\(\s*tokenData/);
});

test("Node timeout signal really aborts a nonresponding backend operation", async () => {
  const signal = AbortSignal.timeout(10);
  const aborted = new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  });
  await assert.rejects(aborted, (error) => error?.name === "TimeoutError");
});
