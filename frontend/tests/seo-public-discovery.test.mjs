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
  assert.match(sitemap, /\["\/", "\/about", "\/how-it-works", "\/demo", "\/help"\]/);
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
  assert.ok(robots.includes('allow: "/"'));
  assert.ok(!robots.includes('disallow: "/"'));
  assert.ok(!robots.includes('disallow: "/login"'));
  assert.ok(!robots.includes('disallow: "/study-abroad"'));
});

test("private workspaces default to noindex while only public pages opt in", () => {
  const layout = source("src/app/layout.tsx");
  assert.ok(layout.includes('metadataBase: new URL("' + production + '")'));
  assert.match(layout, /robots: \{ index: false, follow: false \}/);
  for (const page of ["about", "how-it-works", "demo", "help"]) {
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
  assert.match(about, /WebApplication/);
  assert.match(about, /BusinessApplication/);
  assert.ok(about.includes("JSON.stringify(structuredData).replace"));
  assert.ok(about.includes('href="/demo"'));
  assert.ok(about.includes('href="/register"'));
  assert.ok(about.includes("not admission or visa decisions"));
  const login = source("src/app/login/page.tsx");
  assert.ok(login.includes('href="/about"'));
  const home = source("src/app/page.tsx");
  assert.match(home, /return <PublicHomePage \/>/);
});

test("Vercel preview URLs cannot compete with canonical production SEO", () => {
  const next = source("next.config.ts");
  assert.match(next, /process\.env\.VERCEL_ENV !== "production"/);
  assert.ok(next.includes('"X-Robots-Tag"'));
  assert.ok(next.includes('"noindex, nofollow"'));
  assert.match(next, /Strict-Transport-Security/);
});

test("private application entrypoints never opt into public search indexing", () => {
  for (const route of ["login", "register", "study-abroad", "web", "agent/browser"]) {
    const page = source("src/app/" + route + "/page.tsx");
    assert.ok(!page.includes("robots: { index: true"),
      "Do not index the private " + route + " route");
    assert.ok(!page.includes("alternates: { canonical"),
      "Do not assign a public canonical to " + route);
  }
});

test("public home has indexable metadata while private workspace remains noindex", () => {
  const home = source("src/app/page.tsx");
  const marketing = source("src/components/marketing/public-home.tsx");
  assert.match(home, /export async function generateMetadata/);
  assert.match(home, /getAccessToken\(\)/);
  assert.match(home, /hasSession/);
  assert.match(home, /robots: \{ index: false, follow: false \}/);
  assert.match(home, /robots: \{ index: true, follow: true \}/);
  assert.match(home, /alternates: \{ canonical: "https:\/\/aqlyra-ai\.vercel\.app\/" \}/);
  assert.match(home, /return <PublicHomePage \/>/);
  assert.match(home, /return <ResponsiveWorkspaceShell user=\{user\} \/>/);
  assert.match(home, /redirect\("\/demo"\)/);
  assert.match(marketing, /<h1/);
  assert.match(marketing, /<h2/);
  assert.match(marketing, /application\/ld\+json/);
  for (const path of ["/login", "/register", "/about", "/how-it-works", "/demo", "/help"]) {
    assert.ok(marketing.includes('href="' + path + '"'), path);
  }
  assert.ok(!marketing.includes("fetch("), "Public page must not fetch private user content");
});

test("homepage discovery never requires authentication or a backend request", () => {
  const home = source("src/app/page.tsx");
  const marketing = source("src/components/marketing/public-home.tsx");
  const sitemap = source("src/app/sitemap.ts");
  assert.match(home, /if \(!user\)/);
  assert.match(home, /return <PublicHomePage \/>/);
  assert.ok(!marketing.includes("getAccessToken"));
  assert.ok(!marketing.includes("backendUrl"));
  assert.ok(!marketing.includes("UserResponse"));
  assert.ok(sitemap.includes('"/"'));
  assert.ok(marketing.includes("Aqlyra AI"));
});


test("public how-it-works explains real RAG, limitations and product questions", () => {
  const page = source("src/app/how-it-works/page.tsx");
  assert.match(page, /export const metadata: Metadata/);
  assert.ok(page.includes('https://aqlyra-ai.vercel.app/how-it-works'));
  assert.match(page, /robots: \{ index: true, follow: true \}/);
  assert.match(page, /<h1/);
  assert.match(page, /<h2/);
  assert.match(page, /retrieval-augmented generation/i);
  assert.match(page, /source-grounded/i);
  assert.match(page, /time-sensitive public questions/i);
  assert.match(page, /semantic vector search/i);
  assert.match(page, /scripted walkthrough/i);
  assert.match(page, /not an independent guarantee/i);
  assert.match(page, /private workspace pages are not intended for search-engine indexing/i);
  assert.doesNotMatch(page, /aggregateRating|ratingCount|100% accurate|guaranteed rankings/i);
  assert.doesNotMatch(page, /getAccessToken|backendUrl|cookies\(\)|Authorization|API_KEY/);
});

test("software entity markup has one consistent current public identity", () => {
  const marketing = source("src/components/marketing/public-home.tsx");
  const about = source("src/app/about/page.tsx");
  for (const page of [marketing, about]) {
    assert.match(page, /WebApplication/);
    assert.match(page, /BusinessApplication/);
    assert.ok(page.includes("https://aqlyra-ai.vercel.app/#software"));
    assert.ok(page.includes("https://github.com/naim-munshi/aqlyra-rag-ai"));
    assert.ok(page.includes('JSON.stringify(structuredData).replace'));
    assert.doesNotMatch(page, /aggregateRating|reviewCount|ratingValue|fake reviews/i);
  }
});
