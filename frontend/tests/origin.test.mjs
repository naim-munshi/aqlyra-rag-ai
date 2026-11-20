import assert from "node:assert/strict";
import test from "node:test";

import {
  hasTrustedRequestOrigin,
  isServerSemanticRelayRequest,
} from "../src/lib/security/origin.ts";

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


function relayRequest(path, headers = {}, method = "POST") {
  return new Request("https://aqlyra-ai.vercel.app" + path, {
    method,
    headers: {
      host: "aqlyra-ai.vercel.app",
      "x-forwarded-proto": "https",
      ...headers,
    },
  });
}

const actualRoute = "/api/internal/semantic/v1/embed";
const syntheticBearer = "Bearer synthetic-not-a-real-secret-0000000000000000";

test("only exact non-browser semantic POST with worker bearer passes the server route gate", () => {
  const safe = relayRequest(actualRoute, { authorization: syntheticBearer });
  assert.equal(hasTrustedRequestOrigin(safe), false);
  assert.equal(isServerSemanticRelayRequest(safe), true);
  assert.equal(isServerSemanticRelayRequest(relayRequest(actualRoute)), false);
  assert.equal(isServerSemanticRelayRequest(relayRequest("/api/auth/login", {
    authorization: syntheticBearer,
  })), false);
  assert.equal(isServerSemanticRelayRequest(relayRequest(actualRoute, {
    authorization: syntheticBearer,
  }, "GET")), false);
});

test("relay exception never accepts browser provenance, cookies or malformed auth", () => {
  for (const [name, value] of [
    ["cookie", "session=present"],
    ["origin", "https://aqlyra-ai.vercel.app"],
    ["referer", "https://aqlyra-ai.vercel.app/chat"],
    ["sec-fetch-site", "same-origin"],
    ["sec-fetch-site", "cross-site"],
  ]) {
    assert.equal(isServerSemanticRelayRequest(relayRequest(actualRoute, {
      authorization: syntheticBearer,
      [name]: value,
    })), false, name);
  }
  for (const authorization of ["Bearer short", "Basic xyz", "Bearer xyz,invalid"]) {
    assert.equal(isServerSemanticRelayRequest(relayRequest(actualRoute, {
      authorization,
    })), false);
  }
});

test("normal authenticated same-origin browser flows keep original CSRF behavior", () => {
  const userPost = relayRequest("/api/auth/login", {
    origin: "https://aqlyra-ai.vercel.app",
    "sec-fetch-site": "same-origin",
  });
  assert.equal(hasTrustedRequestOrigin(userPost), true);
  assert.equal(isServerSemanticRelayRequest(userPost), false);
});
