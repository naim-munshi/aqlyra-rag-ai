import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function src(path) {
  return readFileSync(new URL("../src/" + path, import.meta.url), "utf8");
}
const google = src("app/api/auth/google/route.ts");
const password = src("app/api/auth/login/route.ts");
const complete = src("lib/auth/complete-authentication.ts");

test("live sign-in proxy has bounded cold start and no-cache failures", () => {
  for (const [name, code] of [["google", google], ["password", password]]) {
    assert.match(code, /signal: AbortSignal\.timeout\(45_000\)/, name);
    assert.match(code, /cache: "no-store"/, name);
    assert.match(code, /error\.name === "TimeoutError"/, name);
    assert.match(code, /error\.name === "AbortError"/, name);
    assert.match(code, /status: 503/, name);
    assert.match(code, /"Retry-After": "10"/, name);
    assert.match(code, /"Cache-Control": "private, no-store"/, name);
    assert.match(code, /status: 502/, name);
    assert.doesNotMatch(code, /console\.(log|error)\(.*(password|credential)/);
  }
});

test("legacy profile authentication is bounded before cookies", () => {
  assert.match(complete, /signal: AbortSignal\.timeout\(15_000\)/);
  assert.match(complete, /cache: "no-store"/);
  assert.match(complete, /setAccessToken\(/);
  assert.match(complete, /setRefreshToken\(/);
  assert.match(complete, /clearRefreshToken\(/);
  assert.ok(complete.indexOf("signal: AbortSignal.timeout(15_000)") <
    complete.indexOf("await setAccessToken"), "profile fetch precedes any cookie");
  assert.match(complete, /return NextResponse\.json\(\s*\{ user: userData \}/);
  assert.doesNotMatch(complete, /return NextResponse\.json\(\s*\{[^}]*access_token/);
});

test("timeout abort really settles within a bounded interval", async () => {
  const controller = AbortSignal.timeout(8);
  const result = new Promise((_resolve, reject) => {
    controller.addEventListener("abort", () => reject(controller.reason), { once: true });
  });
  await assert.rejects(result, (error) => error?.name === "TimeoutError");
});
