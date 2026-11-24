import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import typescript from "typescript";

const read = path => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");
const helper = read("lib/security/origin.ts");
const compiled = typescript.transpileModule(helper, {
  compilerOptions: { target: typescript.ScriptTarget.ES2022, module: typescript.ModuleKind.CommonJS },
}).outputText;
const context = { exports: {}, URL };
vm.runInNewContext(compiled, context, { timeout: 2000 });
const originAccepted = context.exports.hasTrustedRequestOrigin;

function request({
  origin = null, site = null, referer = null,
  method = "POST", host = "aqlyra-ai.vercel.app",
} = {}) {
  const headers = { host, "x-forwarded-proto": "https" };
  if (origin !== null) headers.origin = origin;
  if (site !== null) headers["sec-fetch-site"] = site;
  if (referer !== null) headers.referer = referer;
  return new Request("https://aqlyra-ai.vercel.app/api/conversations", { method, headers });
}

test("same-origin browser voice and ordinary chat calls remain allowed", () => {
  assert.equal(originAccepted(request({
    origin: "https://aqlyra-ai.vercel.app", site: "same-origin",
  })), true);
  assert.equal(originAccepted(request({
    site: "same-origin",
  })), true);
  assert.equal(originAccepted(request({
    referer: "https://aqlyra-ai.vercel.app/chat", site: "none",
  })), true);
});

test("cross-site, same-site subdomain and spoofed origin are rejected", () => {
  assert.equal(originAccepted(request({
    origin: "https://evil.invalid", site: "cross-site",
  })), false);
  assert.equal(originAccepted(request({
    origin: "https://aqlyra-ai.vercel.app", site: "same-site",
  })), false);
  assert.equal(originAccepted(request({
    origin: "https://aqlyra-ai.vercel.app.evil.invalid", site: "none",
  })), false);
  assert.equal(originAccepted(request({
    origin: "https://evil.invalid", referer: "https://aqlyra-ai.vercel.app/chat",
  })), false);
  assert.equal(originAccepted(request()), false, "missing browser-origin proof must fail closed");
});

test("voice token and voice-backed conversation writes require origin checks", () => {
  const files = [
    "app/api/voice/session/route.ts",
    "app/api/conversations/route.ts",
    "app/api/conversations/[conversationId]/messages/route.ts",
  ];
  for (const file of files) {
    const source = read(file);
    assert.match(source, /hasTrustedRequestOrigin\(request\)/, file);
    assert.match(source, /Untrusted request origin/, file);
    assert.match(source, /status: 403/, file);
    assert.match(source, /getAccessToken\(\)/, file);
  }
});

test("voice-backed chat writes have explicit size bounds", () => {
  const create = read("app/api/conversations/route.ts");
  const messages = read("app/api/conversations/[conversationId]/messages/route.ts");
  assert.match(create, /readBoundedJson\(request, 16384\)/);
  assert.match(messages, /readBoundedJson\(\s*request,\s*131072/);
  assert.match(messages, /RequestBodyTooLargeError/);
  assert.match(messages, /status: 413/);
  assert.doesNotMatch(messages, /await request\.json\(\)/);
});
