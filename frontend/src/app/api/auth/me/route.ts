import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearAccessToken,
  getAccessToken,
} from "@/lib/auth/session";
import type {
  BackendError,
  UserResponse,
} from "@/types/auth";

export async function GET() {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json(
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
    }

    return NextResponse.json(
      data ?? {
        detail: "Backend returned an invalid response",
      },
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}