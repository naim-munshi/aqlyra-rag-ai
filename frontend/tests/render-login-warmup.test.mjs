import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  waitForBackendReady,
  LOGIN_READINESS_INTERVAL_MS,
  LOGIN_READINESS_MAX_ATTEMPTS,
  LOGIN_READINESS_TIMEOUT_MS,
} from "../src/lib/status/wait-for-backend-ready.ts";

const login = readFileSync(
  new URL("../src/components/auth/login-form.tsx", import.meta.url), "utf8",
);

test("healthy backend completes with exactly one credential-free GET", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (...args) => {
      calls.push(args);
      return new Response(JSON.stringify({ status: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };
    assert.equal(await waitForBackendReady(), true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "/api/health");
    assert.equal(calls[0][1].method, "GET");
    assert.equal(calls[0][1].credentials, "omit");
    assert.equal(calls[0][1].cache, "no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("login never sends credentials before readiness or retries a POST", () => {
  assert.match(login, /useEffect\(\(\) => \{/);
  assert.match(login, /waitForBackendReady\(\)/);
  assert.match(login, /if \(!\(await waitForBackendReady\(\)\)\)/);
  assert.match(login, /Aqlyra is still starting/);
  assert.match(login, /fetch\("\/api\/auth\/login",/);
  assert.ok(login.indexOf("await waitForBackendReady()") <
            login.indexOf('fetch("/api/auth/login"'));
  assert.ok(LOGIN_READINESS_MAX_ATTEMPTS <= 8);
  assert.ok(LOGIN_READINESS_INTERVAL_MS >= 3000);
  assert.ok(LOGIN_READINESS_TIMEOUT_MS <= 12000);
});
