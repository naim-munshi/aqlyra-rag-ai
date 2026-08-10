import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { setAccessToken } from "@/lib/auth/session";
import type {
  BackendError,
  LoginInput,
  TokenResponse,
  UserResponse,
} from "@/types/auth";

export async function POST(request: Request) {
  let body: LoginInput;

  try {
    body = (await request.json()) as LoginInput;
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  try {
    const loginResponse = await fetch(
      backendUrl("/auth/login"),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    const loginData =
      await readJson<TokenResponse | BackendError>(loginResponse);

    if (!loginResponse.ok) {
      return NextResponse.json(
        loginData ?? { detail: "Login failed" },
        { status: loginResponse.status },
      );
    }

    if (
      !loginData ||
      !("access_token" in loginData) ||
      !loginData.access_token
    ) {
      return NextResponse.json(
        { detail: "Backend returned an invalid token response" },
        { status: 502 },
      );
    }

    /*
     * Retrieve the authenticated user BEFORE storing
     * the token in the browser cookie.
     */
    const userResponse = await fetch(
      backendUrl("/users/me"),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${loginData.access_token}`,
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

    await setAccessToken(loginData.access_token);

    return NextResponse.json({
      user: userData,
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}