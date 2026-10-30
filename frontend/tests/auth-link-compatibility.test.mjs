import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

for (const [shortcut, canonical] of [
  ["signup", "register"],
  ["signin", "login"],
]) {
  test(`Shared /${shortcut} link redirects to /${canonical}`, () => {
    const code = readFileSync(
      new URL(`../src/app/${shortcut}/page.tsx`, import.meta.url),
      "utf8",
    );
    assert.match(code, /import\s*\{\s*redirect\s*\}\s*from\s*["']next\/navigation["']/);
    assert.ok(code.includes(`redirect("/${canonical}")`));
    assert.doesNotMatch(code, /NEXT_PUBLIC_AQLYRA_DEMO_ONLY/);
  });
}
