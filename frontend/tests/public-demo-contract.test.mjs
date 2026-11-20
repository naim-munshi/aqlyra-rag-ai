import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/app/demo/page.tsx", import.meta.url), "utf8");
const experience = readFileSync(new URL("../src/app/demo/demo-experience.tsx", import.meta.url), "utf8");
const scenarios = readFileSync(new URL("../src/lib/demo/scenarios.ts", import.meta.url), "utf8");

test("retired /demo route redirects to sign-in and does not render the scripted preview", () => {
  assert.match(page, /redirect\(["']\/login["']\)/);
  assert.doesNotMatch(page, /DemoExperience/);
});

test("archived sample responses remain clearly marked as simulated, not inferred live", () => {
  assert.match(experience, /SIMULATED CONTENT/);
  assert.match(experience, /scripted samples only/i);
  assert.match(scenarios, /NOT responses/);
  assert.doesNotMatch(experience, /fetch\(/);
});

test("archived preview source continues to disclose incomplete modes rather than fabricating availability", () => {
  for (const status of ["LIVE BETA", "BROWSER DEPENDENT", "SAFETY-GATED", "LIMITED CANARY"]) {
    assert.ok(experience.includes(status), status);
  }
  assert.match(experience, /Browser Agent/);
  assert.match(experience, /Production execution remains off/);
  assert.match(experience, /Tavily supplies current public sources/);
});
