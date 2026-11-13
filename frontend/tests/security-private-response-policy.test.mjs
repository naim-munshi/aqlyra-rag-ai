import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { privateJsonResponse } from "../src/lib/security/private-json.ts";

const privateRoutes = [
  "auth/me",
  "projects",
  "conversations",
  "conversations/[conversationId]/messages",
  "documents",
  "documents/[documentId]/units",
];

test("private response helper overrides cache-friendly proxy headers", async () => {
  const response = privateJsonResponse(
    { profile: "synthetic-test-value" },
    {
      status: 200,
      headers: {
        "Cache-Control": "public, s-maxage=3600",
        "Vary": "Accept-Encoding",
        "X-Request-ID": "synthetic-only",
      },
    },
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "private, no-store, max-age=0");
  assert.equal(response.headers.get("Vary"), "Accept-Encoding, Cookie");
  assert.equal(response.headers.get("X-Request-ID"), "synthetic-only");
  assert.deepEqual(await response.json(), { profile: "synthetic-test-value" });

  const alreadyCookie = privateJsonResponse(
    { account: "synthetic-only" },
    { headers: { "Vary": "Cookie, Accept-Language" } },
  );
  assert.equal(alreadyCookie.headers.get("Vary"), "Cookie, Accept-Language");
});

test("personalized account, project, chat and document APIs return only private JSON", () => {
  for (const route of privateRoutes) {
    const content = readFileSync(
      new URL("../src/app/api/" + route + "/route.ts", import.meta.url),
      "utf8",
    );
    assert.match(content, /import \{ privateJsonResponse \} from "@\/lib\/security\/private-json"/);
    assert.match(content, /privateJsonResponse\(/);
    assert.doesNotMatch(content, /NextResponse\.json\(/,
      route + " contains an unprotected browser-facing JSON response");
    assert.match(content, /getAccessToken\(/);
  }
});
