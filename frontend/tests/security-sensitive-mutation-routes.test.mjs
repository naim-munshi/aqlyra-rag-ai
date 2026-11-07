import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (route) => readFileSync(
  new URL("../src/app/api/" + route + "/route.ts", import.meta.url),
  "utf8",
);

test("project and conversation update JSON is bounded before parsing", () => {
  for (const route of ["projects/[projectId]", "conversations/[conversationId]"]) {
    const body = source(route);
    assert.ok(body.includes("hasTrustedRequestOrigin(request)"), route);
    assert.match(body, /readBoundedJson\(request, 16_384\)/);
    assert.match(body, /RequestBodyTooLargeError/);
    assert.match(body, /status: 413/);
    assert.match(body, /status: 403/);
    assert.doesNotMatch(body, /request\.json\(\)/);
    const matches = body.match(/hasTrustedRequestOrigin\(request\)/g) ?? [];
    assert.equal(matches.length, 2, "Both PATCH and DELETE must verify origin: " + route);
    assert.match(body, /export async function DELETE\(/);
  }
});

test("high-risk browser approvals and document workflow endpoints recheck request origin", () => {
  for (const route of [
    "agent/browser/execute", "agent/browser/plan",
    "documents/cloud/[intentId]/finalize",
    "documents/[documentId]/process",
  ]) {
    const body = source(route);
    assert.ok(body.includes('from "@/lib/security/origin"'), route);
    assert.match(body, /hasTrustedRequestOrigin\(/);
    assert.match(body, /status: 403/);
    assert.match(body, /private, no-store/);
  }
});

test("global CSRF gateway continues to apply to every API route", () => {
  const proxy = readFileSync(new URL("../src/proxy.ts", import.meta.url), "utf8");
  assert.ok(proxy.includes('matcher: "/api/:path*"'));
  assert.ok(proxy.includes("hasTrustedRequestOrigin(request)"));
  assert.ok(proxy.includes("isServerSemanticRelayRequest(request)"));
});
