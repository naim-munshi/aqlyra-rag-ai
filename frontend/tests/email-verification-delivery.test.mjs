import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const register = readFileSync(
  new URL("../src/components/auth/register-form.tsx", import.meta.url),
  "utf8",
);
const resendProxy = readFileSync(
  new URL("../src/app/api/auth/resend-verification/route.ts", import.meta.url),
  "utf8",
);

test("signup never claims a code was sent after failed provider dispatch", () => {
  assert.match(register, /verification_email_sent !== true/);
  assert.match(register, /pendingVerificationDelivery/);
  assert.match(register, /could not send the verification email/);
  assert.match(register, /href="\/verify-email"/);
  assert.match(register, /disabled=\{loading \|\| pendingVerificationDelivery\}/);
});

test("verification resend propagates backend failure and does not leak a token", () => {
  assert.match(resendProxy, /backendUrl\("\/auth\/resend-verification"\)/);
  assert.match(resendProxy, /status: response.status/);
  assert.match(resendProxy, /verification_token: verificationToken/);
  assert.match(resendProxy, /clearEmailVerificationToken/);
});
