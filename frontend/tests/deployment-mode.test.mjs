import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { unauthenticatedLanding } from "../src/lib/deployment/mode.ts";

const source = (path) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("legacy demo-only configuration never re-enables the retired public preview", () => {
  for (const option of [undefined, "", "false", "TRUE", "1", "true", "true "]) {
    assert.equal(unauthenticatedLanding(option), "/login");
  }
});

test("the old /demo URL redirects to the real sign-in page without loading sample UI", () => {
  const demoPage = source("../src/app/demo/page.tsx");
  assert.match(demoPage, /redirect\(["']\/login["']\)/);
  assert.doesNotMatch(demoPage, /DemoExperience/);
});

test("login and public marketing pages do not advertise the retired demo", () => {
  for (const path of [
    "../src/app/login/page.tsx",
    "../src/components/marketing/public-home.tsx",
    "../src/app/about/page.tsx",
  ]) {
    assert.doesNotMatch(source(path), /href=["']\/demo["']/);
  }
});

test("the public sitemap and root landing flow do not expose the demo", () => {
  assert.doesNotMatch(source("../src/app/sitemap.ts"), /["']\/demo["']/);
  assert.doesNotMatch(source("../src/app/page.tsx"), /redirect\(["']\/demo["']\)/);
});
