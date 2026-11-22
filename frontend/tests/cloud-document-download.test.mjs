import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/app/api/documents/[documentId]/content/route.ts", import.meta.url),
  "utf8",
);

test("never server-side fetch or buffer private redirect payload", () => {
  assert.match(source, /redirect: "manual"/);
  assert.match(source, /response.status === 307/);
  assert.match(source, /NextResponse.redirect\(target/);
});

test("private signed download links require Neon HTTPS origin", () => {
  assert.match(source, /target.protocol !== "https:"/);
  assert.match(source, /\.aws\.neon\.tech/);
  assert.match(source, /target.username \|\| target.password \|\| target.port/);
  assert.match(source, /"Referrer-Policy": "no-referrer"/);
  assert.match(source, /"Cache-Control": "private, no-store"/);
});
