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

    return privateJsonResponse(
      data ?? {
        detail: "Backend returned an invalid response",
      },
      {
        status: response.status,
      },
    );
  } catch {
    return privateJsonResponse(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}