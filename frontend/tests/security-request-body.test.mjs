import assert from "node:assert/strict";
import test from "node:test";

import {
  readBoundedBodyBytes,
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

test("safe multipart file reconstruction parses bounded binary input", async () => {
  const form = new FormData();
  form.append("file", new Blob(["# Aqlyra safe upload"]), "sample.md");
  const incoming = new Request("https://aqlyra.example/api/documents/upload", {
    method: "POST", body: form,
  });
  const contentType = incoming.headers.get("content-type");
  const bounded = await readBoundedBodyBytes(incoming, 4_096);
  const reconstructed = new Request("https://aqlyra.example/api/documents/upload", {
    method: "POST",
    headers: { "Content-Type": contentType },
    body: new Uint8Array(bounded),
  });
  const parsed = await reconstructed.formData();
  assert.equal(parsed.get("file")?.name, "sample.md");
});

test("oversized multipart body fails before form parsing", async () => {
  const request = new Request("https://aqlyra.example/api/documents/upload", {
    method: "POST", body: new Uint8Array(5_000),
  });
  await assert.rejects(
    readBoundedBodyBytes(request, 4_096),
    RequestBodyTooLargeError,
  );
});
