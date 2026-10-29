import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const source = readFileSync(path.join(root, "src/components/auth/forgot-password-form.tsx"), "utf8");

test("successful OTP reset alone is required before sign in attempt", () => {
  const reset = source.indexOf('fetch("/api/auth/reset-password"');
  const success = source.indexOf("if (!response.ok)", reset);
  const login = source.indexOf('fetch("/api/auth/login"');
  assert.ok(reset >= 0 && success > reset && login > success);
  assert.match(source, /if \(signedIn\) \{\s*router\.replace\("\/"\)/);
  assert.match(source, /setStep\("done"\)/);
  assert.ok(source.includes('setPassword("");'));
  assert.ok(source.includes('setCode("");'));
  assert.doesNotMatch(source, /localStorage\.setItem\([^\n]*token/);
});

test("canonical navigation routes and recovery links exist", () => {
  for (const page of ["login", "forgot-password", "register", "study-abroad"]) {
    assert.ok(existsSync(path.join(root, "src/app", page, "page.tsx")), page);
  }
  assert.ok(existsSync(path.join(root, "src/app/api/auth/login/route.ts")));
  assert.ok(existsSync(path.join(root, "src/app/api/auth/reset-password/route.ts")));
  assert.match(source, /href="\/login"/);
});
