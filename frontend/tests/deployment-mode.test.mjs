import assert from "node:assert/strict";
import test from "node:test";

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
