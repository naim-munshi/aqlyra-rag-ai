import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import type {
  BackendError,
  RegisterInput,
  UserResponse,
} from "@/types/auth";

export async function POST(request: Request) {
  let body: RegisterInput;

  try {
    body = (await request.json()) as RegisterInput;
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  const backendHeaders = new Headers({
    "Content-Type": "application/json",
  });

  const clientIp =
    request.headers.get("x-aqlyra-client-ip");

  if (clientIp) {
    backendHeaders.set(
      "X-Aqlyra-Client-IP",
      clientIp,
    );
  }

  try {
    const response = await fetch(
      backendUrl("/auth/register"),
      {
        method: "POST",
        headers: backendHeaders,
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    const data =
      await readJson<UserResponse | BackendError>(response);

    const retryAfter =
      response.headers.get("retry-after");

    const responseHeaders = new Headers();

    if (retryAfter) {
      responseHeaders.set(
        "Retry-After",
        retryAfter,
      );
    }

    return NextResponse.json(
      data ?? {
        detail: "Backend returned an invalid response",
      },
      {
        status: response.status,
        headers: responseHeaders,
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}