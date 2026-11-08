import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearEmailVerificationToken,
  clearRefreshToken,
  setAccessToken,
  setRefreshToken,
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
    const responseHeaders = new Headers();

    if (retryAfter) {
      responseHeaders.set("Retry-After", retryAfter);
    }

    return NextResponse.json(
      tokenData ?? { detail: fallbackError },
      {
        status: tokenResponse.status,
        headers: responseHeaders,
      },
    );
  }

  if (
    !tokenData ||
    !("access_token" in tokenData) ||
    !tokenData.access_token
  ) {
    return NextResponse.json(
      { detail: "Backend returned an invalid token response" },
      { status: 502 },
    );
  }

  // Backend now includes the user it already loaded during authentication.
  // Avoid a second Vercel -> Render round-trip on the hot login path.
  let userData: UserResponse | BackendError | null =
    tokenData.user && typeof tokenData.user.id === "string" &&
    typeof tokenData.user.username === "string"
      ? tokenData.user
      : null;

  if (!userData) {
    // Backward compatibility while the API and frontend roll out separately.
    const userResponse = await fetch(
      backendUrl("/users/me"),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
        cache: "no-store",
        // Prevent a second unbounded Vercel -> Render round trip when the
        // backend returns a legacy token response without the user profile.
        signal: AbortSignal.timeout(15_000),
      },
    );
    userData = await readJson<UserResponse | BackendError>(userResponse);
    if (!userResponse.ok) {
      return NextResponse.json(
        userData ?? { detail: "Unable to retrieve authenticated user" },
        { status: userResponse.status },
      );
    }
  }

  const remember = options.remember !== false;
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
