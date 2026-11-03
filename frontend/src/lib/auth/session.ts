import { cookies } from "next/headers";

import { backendUrl } from "@/lib/api/backend";

const ACCESS_TOKEN_COOKIE = "aqlyra_access_token";
const REFRESH_TOKEN_COOKIE = "aqlyra_refresh_token";
const EMAIL_VERIFICATION_COOKIE = "aqlyra_email_verification_token";
const REFRESH_AHEAD_SECONDS = 45;
const MAX_REFRESH_COOKIE_SECONDS = 30 * 24 * 60 * 60;

type SessionOptions = {
  remember?: boolean;
};

function tokenRemainingSeconds(token: string): number | null {
  // Decode expiry only to decide when to *ask the backend* for a new token.
  // This is not an authorization decision: FastAPI verifies JWT signatures,
  // ticket type, user status and the auth_epoch for every request.
  const payload = token.split(".")[1];
  if (!payload) return null;
  try {
    const decoded = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf8"),
    ) as { exp?: unknown };
    if (typeof decoded.exp !== "number" || !Number.isFinite(decoded.exp)) {
      return null;
    }
    return Math.max(0, Math.floor(decoded.exp - Date.now() / 1000));
  } catch {
    return null;
  }
}

const cookieSecurity = {
  httpOnly: true as const,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

export async function setAccessToken(
  token: string,
  options: SessionOptions = {},
) {
  const cookieStore = await cookies();
  const age = tokenRemainingSeconds(token);
  cookieStore.set({
    name: ACCESS_TOKEN_COOKIE,
    value: token,
    ...cookieSecurity,
    ...(options.remember && age !== null && age > 0
      ? { maxAge: age }
      : {}),
  });
}

export async function setRefreshToken(token: string) {
  const cookieStore = await cookies();
  const age = tokenRemainingSeconds(token);
  if (age === null || age <= 0) {
    throw new Error("Invalid refresh-ticket lifetime");
  }
  cookieStore.set({
    name: REFRESH_TOKEN_COOKIE,
    value: token,
    ...cookieSecurity,
    maxAge: Math.min(age, MAX_REFRESH_COOKIE_SECONDS),
  });
}

export async function clearRefreshToken() {
  const cookieStore = await cookies();
  cookieStore.delete(REFRESH_TOKEN_COOKIE);
}

export async function getAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
  const remaining = accessToken ? tokenRemainingSeconds(accessToken) : null;

  if (accessToken && remaining !== null && remaining > REFRESH_AHEAD_SECONDS) {
    return accessToken;
  }

  const refreshTicket = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshTicket) return accessToken;

  let response: Response;
  try {
    response = await fetch(backendUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshTicket }),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    // A transient provider outage must NOT clear a valid local session.
    if (accessToken && remaining !== null && remaining > 0) return accessToken;
    throw new Error("Session service temporarily unavailable");
  }

  if (response.status === 401 || response.status === 403) {
    // Permanent invalidation (logout, password reset, absolute deadline).
    // Server Components cannot mutate cookies; downstream route handlers can.
    try {
      cookieStore.delete(ACCESS_TOKEN_COOKIE);
      cookieStore.delete(REFRESH_TOKEN_COOKIE);
    } catch {
      // A Server Component can still redirect; the cookies expire normally.
    }
    return null;
  }
  if (!response.ok) {
    if (accessToken && remaining !== null && remaining > 0) return accessToken;
    throw new Error("Session service temporarily unavailable");
  }

  let data: { access_token?: unknown };
  try {
    data = (await response.json()) as { access_token?: unknown };
  } catch {
    throw new Error("Session service returned an invalid response");
  }
  if (typeof data.access_token !== "string" || !data.access_token) {
    throw new Error("Session service returned an invalid response");
  }

  const renewed = data.access_token;
  try {
    // Writable API Route Handler: persist the new 30-minute access cookie.
    // Read-only Server Component: use the renewed JWT for this rendering;
    // the next API route can persist it without prompting for a password.
    await setAccessToken(renewed, { remember: true });
  } catch {
    // Next.js prohibits cookie mutation from Server Components.
  }
  return renewed;
}

export async function clearAccessToken() {
  const cookieStore = await cookies();
  cookieStore.delete(ACCESS_TOKEN_COOKIE);
}

export async function setEmailVerificationToken(token: string) {
  const cookieStore = await cookies();
  cookieStore.set({
    name: EMAIL_VERIFICATION_COOKIE,
    value: token,
    ...cookieSecurity,
  });
}

export async function getEmailVerificationToken() {
  const cookieStore = await cookies();
  return cookieStore.get(EMAIL_VERIFICATION_COOKIE)?.value ?? null;
}

export async function clearEmailVerificationToken() {
  const cookieStore = await cookies();
  cookieStore.delete(EMAIL_VERIFICATION_COOKIE);
}
