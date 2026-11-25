import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(
  new URL("../src/" + path, import.meta.url), "utf8",
);

const authRoutes = [
  "register", "login", "google", "verify-email",
  "resend-verification", "request-password-reset",
  "reset-password", "claim-pending-email",
];
const authenticatedJsonRoutes = [
  "agent/browser/plan",
  "agent/browser/execute",
  "web/research",
  "study-abroad/[...path]",
  "chat/normal/stream",
  "voice/session",
  "rag/answer",
  "projects",
  "conversations",
];

test("all public identity routes bound streamed request bytes before JSON parsing", () => {
  for (const name of authRoutes) {
    const route = source("app/api/auth/" + name + "/route.ts");
    assert.match(route, /readBoundedJson\(request\)/, name);
    assert.match(route, /RequestBodyTooLargeError/, name);
    assert.match(route, /status: 413/, name);
    assert.doesNotMatch(route, /request\.json\(\)/, name);
  }
});

test("authenticated AI and workflow endpoints also reject oversized JSON", () => {
  for (const name of authenticatedJsonRoutes) {
    const route = source("app/api/" + name + "/route.ts");
    assert.match(route, /readBoundedJson\(request, [0-9]+\)/, name);
    assert.match(route, /RequestBodyTooLargeError/, name);
    assert.match(route, /status: 413/, name);
    assert.doesNotMatch(route, /request\.json\(\)/, name);
  }
});

test("artifacts, private upload manifest and multipart file parsing are bounded", () => {
  const artifacts = source("lib/api/artifact-proxy.ts");
  const manifest = source("app/api/documents/cloud/prepare/route.ts");
  const multipart = source("app/api/documents/upload/route.ts");
  assert.match(artifacts, /readBoundedBodyText\(request, 35_000\)/);
  assert.match(manifest, /readBoundedJson\(request, 4096\)/);
  assert.match(multipart, /readBoundedBodyBytes\(request, MAX_MULTIPART_BYTES\)/);
  assert.match(multipart, /MAX_FILE_BYTES/);
  assert.match(multipart, /status: 413/);
  assert.doesNotMatch(multipart, /await request\.formData\(\)/);
});
