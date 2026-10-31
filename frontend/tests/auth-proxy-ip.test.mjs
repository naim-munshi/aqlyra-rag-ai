import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const authRoutes = [
  "register",
  "login",
  "google",
  "verify-email",
  "resend-verification",
  "request-password-reset",
  "reset-password",
  "claim-pending-email",
];

test("all public authentication proxies prohibit caller-supplied rate-limit IP spoofing", () => {
  for (const route of authRoutes) {
    const file = path.join(
      testsDir, "..", "src", "app", "api", "auth", route, "route.ts",
    );
    const source = readFileSync(file, "utf8");
    assert.ok(source.includes("trustedProxyClientIp(request)"),
      route + ": must use trusted proxy IP handler");
    assert.equal(
      source.includes('request.headers.get("x-aqlyra-client-ip")'),
      false,
      route + ": untrusted header must not be forwarded",
    );
  }
});
