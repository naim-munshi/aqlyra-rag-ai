import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = (relative) =>
  readFileSync(new URL(`../src/${relative}`, import.meta.url), "utf8");

test("refresh ticket is held only in HttpOnly, secure, same-site cookie", () => {
  const session = source("lib/auth/session.ts");
  assert.match(session, /REFRESH_TOKEN_COOKIE = "aqlyra_refresh_token"/);
  assert.match(session, /httpOnly: true/);
  assert.match(session, /secure: process\.env\.NODE_ENV === "production"/);
  assert.match(session, /sameSite: "lax"/);
  assert.match(session, /maxAge: Math\.min\(age, MAX_REFRESH_COOKIE_SECONDS\)/);
  assert.match(session, /method: "POST"/);
  assert.match(session, /backendUrl\("\/auth\/refresh"\)/);
  assert.doesNotMatch(session, /localStorage|sessionStorage/);
});

test("login never returns a refresh JWT to browser JavaScript", () => {
  const auth = source("lib/auth/complete-authentication.ts");
  assert.match(auth, /setRefreshToken\(tokenData\.refresh_token\)/);
  assert.match(auth, /setAccessToken\(tokenData\.access_token/);
  assert.match(auth, /return NextResponse\.json\(\s*\{ user: userData \}/);
  assert.doesNotMatch(auth, /return NextResponse\.json\(tokenData/);
  assert.match(auth, /tokenData\.user/);
});

test("stay signed in is explicit and enabled by default on personal laptop", () => {
  const login = source("components/auth/login-form.tsx");
  assert.match(login, /useState\(true\)/);
  assert.match(login, /remember_me: rememberMe/);
  assert.match(login, /Keep me signed in on this device/);
  assert.match(login, /router\.replace\("\/"\)/);
  assert.doesNotMatch(login, /router\.refresh/);
});

test("manual logout clears access, refresh and pending verification", () => {
  const logout = source("app/api/auth/logout/route.ts");
  assert.match(logout, /clearAccessToken\(\)/);
  assert.match(logout, /clearRefreshToken\(\)/);
  assert.match(logout, /clearEmailVerificationToken\(\)/);
  assert.match(logout, /backendUrl\("\/auth\/logout"\)/);
});

test("temporary backend outage does not become a 401 signed-out response", () => {
  const me = source("app/api/auth/me/route.ts");
  assert.match(me, /Session service temporarily unavailable/);
  assert.match(me, /status: 503/);
  assert.match(me, /response\.status === 401/);
  const home = source("app/page.tsx");
  assert.match(home, /throw new Error\("Aqlyra is temporarily unavailable/);
});

test("Google sign in avoids duplicate push and refresh navigation", () => {
  const google = source("components/auth/google-sign-in-button.tsx");
  assert.match(google, /router\.replace\("\/"\)/);
  assert.doesNotMatch(google, /router\.refresh/);
});
