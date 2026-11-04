import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const relay = readFileSync(
  new URL("../src/app/api/internal/semantic/v1/embed/route.ts", import.meta.url),
  "utf8",
);

test("private semantic relay has exactly one hard-coded upstream and no open proxy", () => {
  assert.match(relay, /https:\/\/aqlyra-semantic-worker\.onrender\.com\/v1\/embed/);
  assert.match(relay, /const DESTINATION =/);
  assert.doesNotMatch(relay, /request\.nextUrl|request\.url|process\.env\.REMOTE_SEMANTIC_URL/);
  assert.match(relay, /redirect: "manual"/);
  assert.match(relay, /cache: "no-store"/);
});

test("worker remains the authority for bearer auth; relay does not log secrets", () => {
  assert.match(relay, /request\.headers\.get\("authorization"\)/);
  assert.match(relay, /Authorization: authorization/);
  assert.match(relay, /jsonError\(401, "Unauthorized"\)/);
  assert.doesNotMatch(relay, /console\.(log|error)|logger\.|cookies\(|getAccessToken\(/);
  assert.match(relay, /"Cache-Control": "private, no-store/);
});

test("relay strictly bounds input, output, timeout, and response status", () => {
  assert.match(relay, /readBoundedJson\(request, MAX_REQUEST_BYTES\)/);
  assert.match(relay, /RequestBodyTooLargeError/);
  assert.match(relay, /data\.texts\.length > 8/);
  assert.match(relay, /text\.length <= 6000/);
  assert.match(relay, /upstream\.arrayBuffer\(\)/);
  assert.match(relay, /payload\.byteLength > MAX_RESPONSE_BYTES/);
  assert.match(relay, /AbortSignal\.timeout\(55_000\)/);
  assert.match(relay, /\[401, 429, 503\]/);
  assert.match(relay, /"Retry-After"/);
  assert.doesNotMatch(relay, /upstream\.text\(\)|upstream\.json\(\)/);
});
