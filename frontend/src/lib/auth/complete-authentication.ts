import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearEmailVerificationToken,
  setAccessToken,
} from "@/lib/auth/session";
import type {
  BackendError,
  TokenResponse,
  UserResponse,
} from "@/types/auth";

export async function completeAuthentication(
  tokenResponse: Response,
  fallbackError: string,
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

  const userResponse = await fetch(
    backendUrl("/users/me"),
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${tokenData.access_token}`,
      },
      cache: "no-store",
    },
  );

  const userData =
    await readJson<UserResponse | BackendError>(userResponse);

  if (!userResponse.ok) {
    return NextResponse.json(
      userData ?? {
        detail: "Unable to retrieve authenticated user",
      },
      { status: userResponse.status },
    );
  }

  await setAccessToken(tokenData.access_token);
  await clearEmailVerificationToken();

  return NextResponse.json({ user: userData });
}
