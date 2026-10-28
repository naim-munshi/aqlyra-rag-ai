import assert from "node:assert/strict";
import test from "node:test";

import {
  readBoundedBodyText,
  readBoundedJson,
  RequestBodyTooLargeError,
} from "../src/lib/security/request-body.ts";

function jsonRequest(body, headers = {}) {
  return new Request("https://aqlyra.example/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body,
  });
}

test("small legitimate authentication JSON still parses", async () => {
  const value = { email: "user@example.com", password: "safe-passphrase" };
  assert.deepEqual(
    await readBoundedJson(jsonRequest(JSON.stringify(value)), 16_384),
    value,
  );
});

test("undeclared oversized chunked requests fail before JSON parsing", async () => {
  const raw = JSON.stringify({ email: "a".repeat(17_000) });
  await assert.rejects(
    readBoundedJson(jsonRequest(raw), 16_384),
    RequestBodyTooLargeError,
  );
});

test("forged small Content-Length cannot bypass the actual byte cap", async () => {
  const raw = JSON.stringify({ token: "x".repeat(7_000) });
  await assert.rejects(
    readBoundedJson(jsonRequest(raw, { "content-length": "1" }), 4_096),
    RequestBodyTooLargeError,
  );
});

test("over-limit declared Content-Length rejects even with short body", async () => {
  await assert.rejects(
    readBoundedJson(jsonRequest("{}", { "content-length": "999999999" }), 4_096),
    RequestBodyTooLargeError,
  );
});

test("multi-byte input is limited by UTF-8 bytes, not character count", async () => {
  const raw = JSON.stringify({ question: "বাংলা".repeat(1_000) });
  assert.ok(raw.length < 10_000);
  await assert.rejects(
    readBoundedBodyText(jsonRequest(raw), 10_000),
    RequestBodyTooLargeError,
  );
});

test("malformed JSON and invalid UTF-8 are rejected", async () => {
  await assert.rejects(
    readBoundedJson(jsonRequest('{"email":'), 16_384),
    SyntaxError,
  );
  const bytes = new Uint8Array([0xc3, 0x28]);
  await assert.rejects(
    readBoundedBodyText(jsonRequest(bytes), 16_384),
    TypeError,
  );
});
