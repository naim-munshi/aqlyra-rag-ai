import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/app/api/voice/session/route.ts", import.meta.url), "utf8",
);

test("voice token minting is same-origin and requires authenticated session", () => {
  assert.match(source, /hasTrustedRequestOrigin\(request\)/);
  assert.match(source, /Untrusted request origin/);
  assert.match(source, /status: 403/);
  assert.match(source, /getAccessToken\(\)/);
  assert.match(source, /status: 401/);
  assert.match(source, /readBoundedJson\(request, 16384\)/);
  assert.match(source, /private, no-store/);
});

test("voice request only forwards the scoped authenticated session token", () => {
  assert.match(source, /Authorization:/);
  assert.match(source, /backendUrl\(/);
  assert.doesNotMatch(source, /LIVEKIT_API_SECRET|LIVEKIT_API_KEY|NEXT_PUBLIC_LIVEKIT/);
});
