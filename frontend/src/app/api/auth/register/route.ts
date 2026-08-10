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

  try {
    const response = await fetch(
      backendUrl("/auth/register"),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    const data =
      await readJson<UserResponse | BackendError>(response);

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