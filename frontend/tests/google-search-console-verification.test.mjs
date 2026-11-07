import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = readFileSync(
  new URL("../src/app/layout.tsx", import.meta.url), "utf8",
);
const home = readFileSync(
  new URL("../src/app/page.tsx", import.meta.url), "utf8",
);

test("Google Search Console URL-prefix ownership token is emitted from root metadata", () => {
  assert.match(root, /verification:\s*\{\s*google:\s*"m_rTNCg8wozqwUkzSrU0m4zlqwCHaOT04JeNUM26Cp8"/);
  assert.match(root, /metadataBase: new URL\("https:\/\/aqlyra-ai\.vercel\.app"\)/);
  assert.match(root, /robots: \{ index: false, follow: false \}/);
});

test("public homepage is still explicitly indexable, signed-in content is noindex", () => {
  assert.match(home, /generateMetadata/);
  assert.match(home, /hasSession/);
  assert.match(home, /robots: \{ index: false, follow: false \}/);
  assert.match(home, /robots: \{ index: true, follow: true \}/);
});
