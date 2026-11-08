import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const routeSource = (name) =>
  readFileSync(
    new URL(`../src/app/api/auth/${name}/route.ts`, import.meta.url),
    "utf8",
  );

for (const name of ["login", "google"]) {
  test(`${name} BFF authentication has a bounded upstream wait`, () => {
    const route = routeSource(name);
    assert.match(route, /signal: AbortSignal\.timeout\(45_000\)/);
    assert.match(route, /error\.name === "TimeoutError"/);
    assert.match(route, /status: 503/);
    assert.match(route, /"Retry-After": "10"/);
    assert.doesNotMatch(route, /status: 504/);
    assert.ok(route.includes(`backendUrl("/auth/${name}")`));
  });
}
