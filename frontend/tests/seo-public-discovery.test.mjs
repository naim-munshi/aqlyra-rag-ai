import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(
  new URL("../" + path, import.meta.url), "utf8",
);
const production = "https://aqlyra-ai.vercel.app";

test("only non-account pages are discoverable in sitemap", () => {
  const sitemap = source("src/app/sitemap.ts");
  assert.match(sitemap, /MetadataRoute\.Sitemap/);
  assert.match(sitemap, /\["\/about", "\/demo", "\/help"\]/);
  for (const privatePath of ["/api", "/study-abroad", "/admin", "/guest", "/login",
    "/register", "/artifacts", "/web", "/agent"]) {
    assert.ok(!sitemap.includes('"' + privatePath + '"'),
      privatePath + " must not appear in the public sitemap");
  }
  assert.ok(sitemap.includes(production));
});

test("robots supplies the canonical sitemap and does not hide noindex pages", () => {
  const robots = source("src/app/robots.ts");
  assert.ok(robots.includes(production));
  assert.ok(robots.includes('disallow: "/api/"'));
  assert.doesNotMatch(robots, /disallow:\\s*["']\\/\\s*["',]/);
  assert.doesNotMatch(robots, /disallow:\s*["']\/login/);
});

test("private workspaces default to noindex while only public pages opt in", () => {
  const layout = source("src/app/layout.tsx");
  assert.ok(layout.includes('metadataBase: new URL("' + production + '")'));
  assert.match(layout, /robots: \{ index: false, follow: false \}/);
  for (const page of ["about", "demo", "help"]) {
    const body = source("src/app/" + page + "/page.tsx");
    assert.match(body, /robots: \{ index: true, follow: true \}/);
    assert.match(body, /alternates: \{ canonical/);
    assert.ok(body.includes(production + "/" + page) ||
      (page === "about" && body.includes(production + "/about")));
    assert.match(body, /openGraph:/);
    assert.match(body, /twitter:/);
  }
  const admin = source("src/app/admin/page.tsx");
  assert.match(admin, /robots: \{ index: false, follow: false \}/);
});

test("Aqlyra public product page is real indexable content, no login or fake outcomes", () => {
  const about = source("src/app/about/page.tsx");
  assert.match(about, /<h1/);
  assert.match(about, /<h2/);
  assert.match(about, /application\/ld\+json/);
  assert.match(about, /SoftwareApplication/);
  assert.match(about, /"\\u003c"/);
  assert.ok(about.includes('href="/demo"'));
  assert.ok(about.includes('href="/register"'));
  assert.ok(about.includes("not admission or visa decisions"));
  const login = source("src/app/login/page.tsx");
  assert.ok(login.includes('href="/about"'));
  const home = source("src/app/page.tsx");
  assert.match(home, /redirect\(unauthenticatedLanding/);
});

test("Vercel preview URLs cannot compete with canonical production SEO", () => {
  const next = source("next.config.ts");
  assert.match(next, /process\.env\.VERCEL_ENV !== "production"/);
  assert.ok(next.includes('"X-Robots-Tag"'));
  assert.ok(next.includes('"noindex, nofollow"'));
  assert.match(next, /Strict-Transport-Security/);
});
