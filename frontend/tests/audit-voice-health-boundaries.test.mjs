import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { privateJsonResponse } from "../src/lib/security/private-json.ts";
import { GET as healthGet } from "../src/app/api/health/route.ts";

const voiceSource = readFileSync(
  new URL("../src/app/api/voice/session/route.ts", import.meta.url), "utf8",
);

test("voice token and failures are never cacheable, including positive response", () => {
  for (const status of [200, 400, 401, 403, 413, 502, 503]) {
    const res = privateJsonResponse(
      { participant_token: "SYNTHETIC-NOT-A-JWT" },
      { status, headers: { "Cache-Control": "public, max-age=3600", "Retry-After": "4" } },
    );
    assert.equal(res.status, status);
    assert.match(res.headers.get("cache-control"), /private, no-store/);
    assert.equal(res.headers.get("pragma"), "no-cache");
    assert.equal(res.headers.get("expires"), "0");
    assert.equal(res.headers.get("retry-after"), "4");
  }
  assert.match(voiceSource, /return privateJsonResponse\(/);
  assert.doesNotMatch(voiceSource, /NextResponse\.json\(/);
  assert.match(voiceSource, /headers:\s*forwardedBackendHeaders\(/);
});

test("frontend readiness maintains no-cache, request ID and retry hints", async () => {
  const originalFetch = globalThis.fetch;
  const oldBackend = process.env.BACKEND_API_URL;
  try {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    globalThis.fetch = async () => new Response(null, {
      status: 200, headers: { "X-Request-ID": "synthetic-id" },
    });
    const ready = await healthGet();
    assert.equal(ready.status, 200);
    assert.equal((await ready.json()).status, "ready");
    assert.equal(ready.headers.get("x-request-id"), "synthetic-id");
    assert.match(ready.headers.get("cache-control"), /no-store/);

    globalThis.fetch = async () => { throw new Error("synthetic cold start"); };
    const warming = await healthGet();
    assert.equal(warming.status, 503);
    assert.equal(warming.headers.get("retry-after"), "10");
    assert.match(warming.headers.get("cache-control"), /no-store/);
    assert.deepEqual(await warming.json(), { status: "unavailable" });

    globalThis.fetch = async () => new Response(null, { status: 503 });
    const notReady = await healthGet();
    assert.equal(notReady.status, 503);
    assert.equal(notReady.headers.get("retry-after"), "10");
  } finally {
    globalThis.fetch = originalFetch;
    if (oldBackend === undefined) delete process.env.BACKEND_API_URL;
    else process.env.BACKEND_API_URL = oldBackend;
  }
});
