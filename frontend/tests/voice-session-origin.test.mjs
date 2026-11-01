import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

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


test("all voice proxy responses explicitly forbid room-token caching", () => {
  assert.match(source, /"Cache-Control": "private, no-store"/);
  assert.match(source, /Pragma: "no-cache"/);
  const tree = ts.createSourceFile(
    "voice-session-route.ts", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS,
  );
  let responseCount = 0;
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.expression.getText(tree) === "NextResponse" &&
      node.expression.name.text === "json"
    ) {
      responseCount += 1;
      const options = node.arguments[1];
      assert.ok(options && ts.isObjectLiteralExpression(options));
      const headers = options.properties.find(
        property => ts.isPropertyAssignment(property) &&
          property.name.getText(tree) === "headers",
      );
      assert.ok(headers, "a voice response is missing cache-control headers");
      assert.match(headers.getText(tree), /PRIVATE_VOICE_HEADERS/);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  assert.equal(responseCount, 7, "check every success and failure path");
});
