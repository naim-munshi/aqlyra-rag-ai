import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const login = read("../src/app/login/page.tsx");
const guestPage = read("../src/app/guest/page.tsx");
const guest = read("../src/components/guest/guest-chat.tsx");
const proxy = read("../src/app/api/guest/chat/route.ts");
const admin = read("../src/app/api/admin/guest-traffic/route.ts");

test("real login offers a guest chat path instead of scripted demo", () => {
  assert.match(login, /href="\/guest"/);
  assert.match(login, /Continue without login/);
});

test("guest UI explicitly gates uploads and discloses short IP retention", () => {
  assert.match(guest, /href="\/register"/);
  assert.match(guest, /Paperclip/);
  assert.match(guest, /IP address/);
  assert.match(guest, /24 hours/);
  assert.match(guest, /not saved/);
  assert.match(guest, /\/api\/guest\/chat/);
  assert.doesNotMatch(guest, /localStorage/);
});

test("guest proxy signs body and Vercel-controlled IP, not browser headers", () => {
  assert.match(proxy, /process\.env\.VERCEL === "1"/);
  assert.match(proxy, /x-vercel-forwarded-for/);
  assert.match(proxy, /createHmac\("sha256", secret\)/);
  assert.match(proxy, /createHash\("sha256"\)/);
  assert.match(proxy, /X-Aqlyra-Guest-Signature/);
  assert.match(proxy, /backendUrl\("\/guest\/chat"\)/);
  assert.match(proxy, /"Cache-Control": "private, no-store"/);
  assert.doesNotMatch(proxy, /getAccessToken/);
});

test("guest IP admin proxy requires an authenticated JWT cookie", () => {
  assert.match(admin, /getAccessToken/);
  assert.match(admin, /if \(!token\)/);
  assert.match(admin, /backendUrl\("\/admin\/guest-traffic"\)/);
});


test("real guest chat only appears after public release flag is enabled", () => {
  assert.match(login, /NEXT_PUBLIC_AQLYRA_GUEST_ENABLED === "true"/);
  assert.match(guestPage, /NEXT_PUBLIC_AQLYRA_GUEST_ENABLED !== "true"/);
  assert.match(guestPage, /redirect\("\/login"\)/);
});
