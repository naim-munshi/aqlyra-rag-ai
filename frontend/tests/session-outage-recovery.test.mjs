import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL("../src/" + path, import.meta.url), "utf8");

test("home does not turn expired-session provider downtime into a 500 or public home", () => {
  const code = source("app/page.tsx");
  assert.match(code, /signal: AbortSignal\.timeout\(12_000\)/);
  assert.match(code, /throw new Error\("Aqlyra is temporarily unavailable/);
  assert.match(code, /catch \{\s*return <SessionServiceUnavailable \/>;\s*\}/);
  assert.match(code, /getAccessToken\(\{ allowRefresh: false \}\)/);
  assert.match(code, /if \(await hasRefreshToken\(\)\) \{\s*throw new Error\("Session renewal required"\)/);
  assert.match(code, /hasSession = Boolean\(accessToken\) \|\| await hasRefreshToken\(\)/);
  assert.match(code, /catch \{[\s\S]*?return \{ robots: \{ index: false, follow: false \} \};/);
});

test("admin and Study Abroad keep cookies and avoid logout on service errors", () => {
  const admin = source("app/admin/page.tsx");
  const study = source("app/study-abroad/page.tsx");
  for (const code of [admin, study]) {
    assert.match(code, /try \{\s*token = await getAccessToken\(\{ allowRefresh: false \}\);\s*\} catch \{[\s\S]*?return <SessionServiceUnavailable \/>;/);
    assert.match(code, /if \(!token\) \{[\s\S]*?hasRefreshToken\(\)[\s\S]*?return <SessionServiceUnavailable \/>;[\s\S]*?redirect\("\/login"\)/);
    assert.doesNotMatch(code, /clearAccessToken\(|clearRefreshToken\(/);
  }
  assert.match(study, /signal: AbortSignal\.timeout\(12_000\)/);
  assert.match(study, /response\.status === 401 \|\| response\.status === 403/);
  assert.match(study, /if \(!response\.ok\) return <SessionServiceUnavailable \/>/);
  assert.doesNotMatch(study, /if \(!active\) redirect\("\/login"\)/);
  assert.match(admin, /response\.status === 403\) notFound\(/);

  // All private server-rendered pages must avoid rotating cookies during render.
  for (const route of ["agent/browser", "web"]) {
    const page = source("app/" + route + "/page.tsx");
    assert.match(page, /getAccessToken\(\{ allowRefresh: false \}\)/);
    assert.match(page, /hasRefreshToken\(\)/);
    assert.match(page, /return <SessionServiceUnavailable \/>/);
    assert.match(page, /response\.status === 401 \|\| response\.status === 403/);
    assert.doesNotMatch(page, /getAccessToken\(\)/);
  }
});

test("session outage is a retryable, non-authenticated view", () => {
  const component = source("components/status/session-service-unavailable.tsx");
  assert.match(component, /role="alert"/);
  assert.match(component, /window\.location\.reload\(\)/);
  assert.doesNotMatch(component, /clearRefreshToken\(/);
});

test("all artifact JSON responses are private even on unauthenticated and 502 paths", () => {
  const proxy = source("lib/api/artifact-proxy.ts");
  assert.match(proxy, /import \{ privateJsonResponse \} from "@\/lib\/security\/private-json"/);
  assert.doesNotMatch(proxy, /NextResponse\.json\(/);
  assert.match(proxy, /return privateJsonResponse\(\{ detail: "Not authenticated" \}, \{ status: 401 \}\)/);
  assert.match(proxy, /"Cache-Control": "private, no-store"/);
  assert.match(proxy, /"Vary": "Cookie"/);
});
