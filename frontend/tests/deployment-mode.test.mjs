import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { unauthenticatedLanding } from "../src/lib/deployment/mode.ts";

test("an explicit demo-only build shows portfolio preview", () => {
  assert.equal(unauthenticatedLanding("true"), "/demo");
});

test("real-software mode routes to login", () => {
  for (const option of [undefined, "", "false", "TRUE", "1"]) {
    assert.equal(unauthenticatedLanding(option), "/login");
  }
});

test("unexpected values do not accidentally enable demo-only mode", () => {
  assert.equal(unauthenticatedLanding("true "), "/login");
});


test("real production never serves the scripted demo page", () => {
  const source = readFileSync(
    new URL("../src/app/demo/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /NEXT_PUBLIC_AQLYRA_DEMO_ONLY !== "true"/);
  assert.match(source, /redirect\("\/login"\)/);
});
