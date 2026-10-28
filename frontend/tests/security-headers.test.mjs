import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const source = readFileSync(
  new URL("../next.config.ts", import.meta.url), "utf8",
);

test("production security response headers protect from framing and MIME sniffing", () => {
  assert.match(source, /frame-ancestors 'none'/);
  assert.match(source, /object-src 'none'/);
  assert.match(source, /X-Frame-Options/);
  assert.match(source, /DENY/);
  assert.match(source, /X-Content-Type-Options/);
  assert.match(source, /nosniff/);
});

test("HSTS is enabled for production without dangerous preloading", () => {
  assert.match(source, /Strict-Transport-Security/);
  assert.match(source, /max-age=31536000/);
  assert.match(source, /process\.env\.NODE_ENV === "production"/);
  assert.doesNotMatch(source, /includeSubDomains/);
  assert.doesNotMatch(source, /\bpreload\b/);
});

test("unused privileged browser APIs are denied without blocking voice or camera", () => {
  assert.match(source, /Permissions-Policy/);
  for (const permission of ["geolocation=()", "payment=()", "usb=()", "serial=()"]) {
    assert.ok(source.includes(permission), permission);
  }
  assert.doesNotMatch(source, /(?:microphone|camera)=\(\)/);
});
