import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { isValidUserIdentity } from "@/lib/auth/user-response";
import {
  clearEmailVerificationToken,
  clearRefreshToken,
  setAccessToken,
  setRefreshToken,
  tokenRemainingSeconds,
} from "@/lib/auth/session";
import type {
  BackendError,
  TokenResponse,
  UserResponse,
} from "@/types/auth";

export async function completeAuthentication(
  tokenResponse: Response,
  fallbackError: string,
  options: { remember?: boolean } = {},
) {
  const tokenData =
    await readJson<TokenResponse | BackendError>(tokenResponse);

  if (!tokenResponse.ok) {
    const retryAfter =
      tokenResponse.headers.get("retry-after");
    const responseHeaders = new Headers({ "Cache-Control": "private, no-store" });

    if (retryAfter) {
      responseHeaders.set("Retry-After", retryAfter);
    }

    return NextResponse.json(
      // Never echo upstream validation inputs (which can contain credentials)
      // or arbitrary token/profile fields on a failed authentication response.
      { detail: tokenResponse.status < 500 && tokenData &&
          typeof tokenData === "object" && "detail" in tokenData &&
          typeof tokenData.detail === "string" ? tokenData.detail : fallbackError },
      {
        status: tokenResponse.status,
        headers: responseHeaders,
      },
    );
  }

  if (
    !tokenData ||
    typeof tokenData !== "object" ||
    Array.isArray(tokenData) ||
    !("access_token" in tokenData) ||
    typeof tokenData.access_token !== "string" ||
    (tokenRemainingSeconds(tokenData.access_token) ?? 0) <= 0
  ) {
    return NextResponse.json(
      { detail: "Backend returned an invalid token response" },
      { status: 502, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  // Backend now includes the user it already loaded during authentication.
  // Avoid a second Vercel -> Render round-trip on the hot login path.
  let userData: UserResponse | BackendError | null = tokenData.user ?? null;

  if (tokenData.user == null) {
    // Backward compatibility while the API and frontend roll out separately.
    const userResponse = await fetch(
      backendUrl("/users/me"),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
        cache: "no-store",
        // Legacy API without user profile: bound this secondary private hop.
        // A failure must abort before any auth cookie is written.
        signal: AbortSignal.timeout(15_000),
      },
    );
    userData = await readJson<UserResponse | BackendError>(userResponse);
    if (!userResponse.ok) {
      return NextResponse.json(
        { detail: "Unable to retrieve authenticated user" },
        { status: userResponse.status, headers: { "Cache-Control": "private, no-store" } },
      );
    }
  }

  const remember = options.remember !== false;
  // Validate everything before the first mutation: an invalid legacy 200 or
  // refresh ticket must not leave a partially authenticated browser session.
  if (!isValidUserIdentity(userData) ||
      (remember && tokenData.refresh_token != null &&
       (typeof tokenData.refresh_token !== "string" ||
        (tokenRemainingSeconds(tokenData.refresh_token) ?? 0) <= 0))) {
    return NextResponse.json(
      { detail: "Backend returned an invalid authentication response" },
      { status: 502, headers: { "Cache-Control": "private, no-store" } },
    );
  }
  await setAccessToken(tokenData.access_token, { remember });
  if (remember && typeof tokenData.refresh_token === "string" &&
      tokenData.refresh_token) {
    await setRefreshToken(tokenData.refresh_token);
  } else {
    // Shared/public machine or legacy API: never retain an old ticket.
    await clearRefreshToken();
  }
  await clearEmailVerificationToken();

  // Sensitive bearer tokens must never be returned to browser JS.
  return NextResponse.json(
    { user: userData },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
