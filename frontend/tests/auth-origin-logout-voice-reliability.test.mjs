import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { isValidUserIdentity } from "../src/lib/auth/user-response.ts";
import { hasTrustedRequestOrigin } from "../src/lib/security/origin.ts";

const source = path => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

const authMutations = [
  "login", "register", "google", "logout", "verify-email",
  "resend-verification", "claim-pending-email",
  "request-password-reset", "reset-password",
];

test("all 9 account-mutating BFF routes require same-origin provenance before any side effects", () => {
  for (const route of authMutations) {
    const code = source("app/api/auth/" + route + "/route.ts");
    const originCheck = code.indexOf("if (!hasTrustedRequestOrigin(request))");
    assert.ok(originCheck > 0, route + " must validate origin");
    assert.ok(code.includes('status: 403'), route + " must reject untrusted origin");
    assert.ok(code.includes('"Cache-Control": "private, no-store"'), route + " must not cache rejection");
    const sideEffect = code.indexOf("readBoundedJson(request)") >= 0
      ? code.indexOf("readBoundedJson(request)")
      : code.indexOf("getAccessToken()");
    assert.ok(sideEffect > originCheck, route + " must reject before reading state");
  }

  const valid = new Request("https://aqlyra-ai.vercel.app/api/auth/login", {
    method: "POST",
    headers: {
      host: "aqlyra-ai.vercel.app",
      "x-forwarded-proto": "https",
      origin: "https://aqlyra-ai.vercel.app",
      "sec-fetch-site": "same-origin",
    },
  });
  assert.equal(hasTrustedRequestOrigin(valid), true);
  assert.equal(hasTrustedRequestOrigin(new Request(valid.url, {
    method: "POST",
    headers: {
      host: "aqlyra-ai.vercel.app",
      "x-forwarded-proto": "https",
      origin: "https://attack.invalid",
      "sec-fetch-site": "cross-site",
    },
  })), false);
});

test("logout clears all cookies even if backend token refresh fails", () => {
  const code = source("app/api/auth/logout/route.ts");
  assert.match(code, /try \{\s*token = await getAccessToken\(\);\s*\} catch \{\s*sessionLookupFailed = true;/);
  assert.match(code, /let revoked = !token && !sessionLookupFailed;/);
  assert.match(code, /signal: AbortSignal\.timeout\(8_000\)/);
  const firstClear = code.indexOf("await clearAccessToken()");
  assert.ok(firstClear > code.indexOf("if (token) {"), "cookie cleanup must be unconditional");
  assert.ok(code.indexOf("await clearRefreshToken()") > firstClear);
  assert.ok(code.indexOf("await clearEmailVerificationToken()") > firstClear);
  assert.ok(code.indexOf("if (!hasTrustedRequestOrigin(request))") < code.indexOf("getAccessToken()"));
});

test("voice status handles refresh errors, bounded upstream calls and malformed success", () => {
  const code = source("app/api/voice/status/route.ts");
  assert.match(code, /try \{\s*token = await getAccessToken\(\);\s*\} catch \{/);
  assert.match(code, /signal: AbortSignal\.timeout\(12_000\)/);
  assert.match(code, /"Retry-After": "10"/);
  assert.match(code, /status: response\.ok && !valid \? 502 : response\.status/);
  assert.doesNotMatch(code, /clearRefreshToken\(|clearAccessToken\(/);
});

const validUser = {
  id: "synthetic-account-id",
  username: "syntheticuser",
  email: "synthetic@example.test",
  is_active: true,
  email_verified_at: null,
  created_at: "2026-11-12T00:00:00Z",
  updated_at: "2026-11-12T00:00:00Z",
};
test("home rejects malformed, disabled and missing identity without logging out", () => {
  assert.equal(isValidUserIdentity(validUser), true);
  for (const malformed of [
    null, {}, [], "synthetic",
    { ...validUser, id: "" },
    { ...validUser, username: "" },
    { ...validUser, email: "" },
    { ...validUser, is_active: false },
    { ...validUser, is_active: undefined },
    { ...validUser, email_verified_at: 5 },
    { ...validUser, created_at: undefined },
    { ...validUser, updated_at: null },
  ]) {
    assert.equal(isValidUserIdentity(malformed), false);
  }
  const home = source("app/page.tsx");
  assert.match(home, /if \(!isValidUserIdentity\(data\)\)/);
  assert.match(home, /return <SessionServiceUnavailable \/>;/);
  assert.doesNotMatch(home, /clearAccessToken\(|clearRefreshToken\(/);
});
