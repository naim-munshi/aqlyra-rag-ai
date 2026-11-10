import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("home does not turn expired-session provider downtime into a 500 or public home", () => {
  const code = source("app/page.tsx");
  assert.match(code, /signal: AbortSignal\.timeout\(12_000\)/);
  assert.match(code, /throw new Error\("Aqlyra is temporarily unavailable/);
  assert.match(code, /catch \{\s*return <SessionServiceUnavailable \/>;\s*\}/);
  assert.match(code, /getAccessToken\(\)/);
  assert.match(code, /catch \{[\s\S]*?return \{ robots: \{ index: false, follow: false \} \};/);
});

test("admin and Study Abroad keep cookies and avoid logout on service errors", () => {
  const admin = source("app/admin/page.tsx");
  const study = source("app/study-abroad/page.tsx");
  for (const code of [admin, study]) {
    assert.match(code, /try \{\s*token = await getAccessToken\(\);\s*\} catch \{\s*return <SessionServiceUnavailable \/>;/);
    assert.match(code, /if \(!token\) redirect\("\/login"\)/);
    assert.doesNotMatch(code, /clearAccessToken\(|clearRefreshToken\(/);
  }
  assert.match(study, /signal: AbortSignal\.timeout\(12_000\)/);
  assert.match(study, /response\.status === 401 \|\| response\.status === 403/);
  assert.match(study, /if \(!response\.ok\) return <SessionServiceUnavailable \/>/);
  assert.doesNotMatch(study, /if \(!active\) redirect\("\/login"\)/);
  assert.match(admin, /response\.status === 403\) notFound\(/);
});

test("session outage is a retryable, non-authenticated view", () => {
  const component = source("components/status/session-service-unavailable.tsx");
  assert.match(component, /role="alert"/);
  assert.match(component, /window\.location\.reload\(\)/);
  assert.doesNotMatch(component, /logout|clearRefreshToken\(/i);
});

test("all artifact JSON responses are private even on unauthenticated and 502 paths", () => {
  const proxy = source("lib/api/artifact-proxy.ts");
  assert.match(proxy, /import \{ privateJsonResponse \} from "@\/lib\/security\/private-json"/);
  assert.doesNotMatch(proxy, /NextResponse\.json\(/);
  assert.match(proxy, /return privateJsonResponse\(\{ detail: "Not authenticated" \}, \{ status: 401 \}\)/);
  assert.match(proxy, /"Cache-Control": "private, no-store"/);
  assert.match(proxy, /"Vary": "Cookie"/);
});
