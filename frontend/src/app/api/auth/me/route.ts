import { privateJsonResponse } from "@/lib/security/private-json";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearAccessToken,
  clearRefreshToken,
  getAccessToken,
} from "@/lib/auth/session";
import type {
  BackendError,
  UserResponse,
} from "@/types/auth";

export async function GET() {
  let token: string | null;
  try {
    token = await getAccessToken();
  } catch {
    // A transient Render outage is not an authentication failure.
    return privateJsonResponse(
      { detail: "Session service temporarily unavailable. Please retry." },
      { status: 503, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  if (!token) {
    return privateJsonResponse(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  try {
    const response = await fetch(
      backendUrl("/users/me"),
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
        // Avoid a Vercel function hanging during Render Free cold starts.
        // A timeout is not evidence of an expired or revoked user session.
        signal: AbortSignal.timeout(12_000),
      },
    );

    const data =
      await readJson<UserResponse | BackendError>(response);

    if (
      response.status === 401 ||
      response.status === 403
    ) {
      await clearAccessToken();
      await clearRefreshToken();
    }

    // A 200 with malformed/missing identity is an upstream failure, not
    // successful authentication. Never let clients mistake it for a user.
    if (
      response.ok &&
      (
        !data ||
        typeof data !== "object" ||
        typeof (data as UserResponse).id !== "string" ||
        !(data as UserResponse).id ||
        typeof (data as UserResponse).email !== "string" ||
        typeof (data as UserResponse).username !== "string"
      )
    ) {
      return privateJsonResponse(
        { detail: "Backend returned an invalid user response" },
        { status: 502 },
      );
    }

    return privateJsonResponse(
      data ?? { detail: "Backend returned an invalid response" },
      { status: response.status },
    );
  } catch (error) {
    // Keep HttpOnly cookies intact on transport/timeouts. A retry can
    // recover the same authenticated session after Render wakes up.
    const isTimeout =
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError");
    return privateJsonResponse(
      {
        detail: isTimeout
          ? "Session service temporarily unavailable. Please retry."
          : "Backend service is unavailable",
      },
      {
        status: isTimeout ? 503 : 502,
        headers: isTimeout ? { "Retry-After": "10" } : {},
      },
    );
  }
}