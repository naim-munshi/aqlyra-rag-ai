import assert from "node:assert/strict";
import test from "node:test";

import { hasTrustedRequestOrigin } from "../src/lib/security/origin.ts";

const publicOrigin = "https://app.example.com";

function request(method, headers = {}) {
  return new Request(publicOrigin + "/api/documents/upload", {
    method,
    headers: {
      host: "app.example.com",
      "x-forwarded-proto": "https",
      ...headers,
    },
  });
}

test("safe GET requests are unaffected", () => {
  assert.equal(hasTrustedRequestOrigin(request("GET")), true);
});

test("same-origin POST, PATCH, and DELETE are accepted", () => {
  for (const method of ["POST", "PATCH", "DELETE"]) {
    assert.equal(
      hasTrustedRequestOrigin(request(method, {
        origin: publicOrigin,
        "sec-fetch-site": "same-origin",
      })),
      true,
    );
  }
});

test("HTTP backend behind HTTPS proxy accepts public HTTPS origin", () => {
  const incoming = new Request("http://app.example.com/api/auth/login", {
    method: "POST",
    headers: {
      host: "app.example.com",
      "x-forwarded-proto": "https",
      origin: publicOrigin,
    },
  });

  assert.equal(hasTrustedRequestOrigin(incoming), true);
});

test("rejects different origin and forged same-site subdomain", () => {
  for (const origin of [
    "https://evil.example.com",
    "https://app.example.com.evil.test",
    "http://app.example.com",
    "null",
  ]) {
    assert.equal(
      hasTrustedRequestOrigin(request("POST", { origin })),
      false,
    );
  }
});

test("rejects cross-site and same-site fetch provenance", () => {
  for (const site of ["cross-site", "same-site"]) {
    assert.equal(
      hasTrustedRequestOrigin(request("POST", {
        origin: publicOrigin,
        "sec-fetch-site": site,
      })),
      false,
    );
  }
});

test("rejects state changes without browser provenance", () => {
  assert.equal(hasTrustedRequestOrigin(request("POST")), false);
  assert.equal(
    hasTrustedRequestOrigin(request("POST", { origin: "" })),
    false,
  );
});

test("accepts verified same-origin fetch metadata or referer", () => {
  assert.equal(
    hasTrustedRequestOrigin(request("POST", {
      "sec-fetch-site": "same-origin",
    })),
    true,
  );
  assert.equal(
    hasTrustedRequestOrigin(request("POST", {
      referer: publicOrigin + "/chat",
    })),
    true,
  );
  assert.equal(
    hasTrustedRequestOrigin(request("POST", {
      referer: "https://evil.example.com/phishing",
    })),
    false,
  );
});
