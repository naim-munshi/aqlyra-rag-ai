import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const get = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("admin page authenticates before reading monitoring data", () => {
  const page = get("../src/app/admin/page.tsx");
  assert.match(page, /getAccessToken\(/);
  assert.match(page, /if \(!token\) redirect\("\/login"\)/);
  assert.match(page, /response\.status === 403\) notFound\(/);
  assert.match(page, /cache: "no-store"/);
  assert.match(page, /index: false/);
});

test("admin JSON proxy checks session and never caches responses", () => {
  const api = get("../src/app/api/admin/overview/route.ts");
  assert.match(api, /getAccessToken\(/);
  assert.match(api, /Not authenticated/);
  assert.match(api, /response\.status === 401 \|\| response\.status === 403/);
  assert.match(api, /Cache-Control": "private, no-store/);
  assert.doesNotMatch(api, /NEXT_PUBLIC_ADMIN/i);
});

test("monitor shows only process-local API traffic, not unique visitors", () => {
  const ui = get("../src/components/admin/admin-monitor.tsx");
  assert.match(ui, /single|per backend process/i);
  assert.match(ui, /not unique website visitors/i);
  assert.doesNotMatch(ui, /localStorage|document\.cookie/);
});
