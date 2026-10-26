import assert from "node:assert/strict";
import test from "node:test";

import { trustedProxyClientIp } from "../src/lib/security/client-ip.ts";

function request(ip) {
  const headers = ip === null ? {} : { "X-Aqlyra-Client-IP": ip };
  return new Request("https://app.example.com/api/auth/login", {
    method: "POST",
    headers,
  });
}

test("untrusted browser client-IP header is never forwarded", () => {
  assert.equal(trustedProxyClientIp(request("198.51.100.10"), false), null);
});

test("trusted Caddy header forwards syntactically valid IPs", () => {
  for (const ip of ["198.51.100.10", "2001:db8::1", "::1"]) {
    assert.equal(trustedProxyClientIp(request(ip), true), ip);
  }
});

test("trusted-header mode rejects lists, ports and invalid data", () => {
  for (const ip of [
    "198.51.100.10, 203.0.113.9",
    "198.51.100.10:4000",
    "not-an-ip",
    "",
  ]) {
    assert.equal(trustedProxyClientIp(request(ip), true), null);
  }
});

test("no client-IP header is acceptable in either mode", () => {
  assert.equal(trustedProxyClientIp(request(null), false), null);
  assert.equal(trustedProxyClientIp(request(null), true), null);
});
