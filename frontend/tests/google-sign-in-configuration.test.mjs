import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = readFileSync(
  new URL("../src/components/auth/google-sign-in-button.tsx", import.meta.url),
  "utf8",
);
const backendRoute = readFileSync(
  new URL("../src/app/api/auth/google/route.ts", import.meta.url), "utf8",
);

test("unconfigured Google sign-in is visible but noninteractive", () => {
  assert.match(source, /if \(!clientId\)/);
  assert.match(source, /data-google-oauth-status="not-configured"/);
  assert.match(source, /\bdisabled\b/);
  assert.match(source, /aria-disabled="true"/);
  assert.match(source, /Google sign-in is not configured yet/);
  assert.doesNotMatch(source, /if \(!clientId\) \{\s*return null/);
});

test("configured Google sign-in still verifies ID token through backend", () => {
  assert.match(source, /google\.accounts\.id\.initialize/);
  assert.match(source, /google\.accounts\.id\.renderButton/);
  assert.match(source, /fetch\("\/api\/auth\/google"/);
  assert.match(backendRoute, /backendUrl\("\/auth\/google"\)/);
  assert.match(backendRoute, /completeAuthentication/);
  assert.doesNotMatch(source, /GOOGLE_CLIENT_SECRET/);
});

test("Google script failure is explained rather than silently hidden", () => {
  assert.match(source, /onError=\{\(\) => setError/);
  assert.match(source, /Open this page in Safari or Chrome/);
});
