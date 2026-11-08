import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

import { trustedProxyClientIp } from "@/lib/security/client-ip";

import { backendUrl } from "@/lib/api/backend";
import { completeAuthentication } from "@/lib/auth/complete-authentication";
import type {
  LoginInput,
} from "@/types/auth";

export async function POST(request: Request) {
  let body: LoginInput;

  try {
    body = (await readBoundedJson(request)) as LoginInput;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return NextResponse.json({ detail: "Request body too large" }, { status: 413 });
    }
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  const backendHeaders = new Headers({
    "Content-Type": "application/json",
  });

  const clientIp = trustedProxyClientIp(request);

  if (clientIp) {
    backendHeaders.set("X-Aqlyra-Client-IP", clientIp);
  }

  try {
    const loginResponse = await fetch(
      backendUrl("/auth/login"),
      {
        method: "POST",
        headers: backendHeaders,
        // Persistence is first-party BFF policy, never an auth-provider
        // permission or an extra field in the password validation request.
        body: JSON.stringify({
          email: body.email,
          password: body.password,
        }),
        cache: "no-store",
        // Bound cold-start / upstream stalls before Vercel kills the function.
        signal: AbortSignal.timeout(45_000),
      },
    );

    return await completeAuthentication(
      loginResponse,
      "Login failed",
      { remember: body.remember_me !== false },
    );
  } catch (error) {
    const timedOut = error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError");
    if (timedOut) {
      return NextResponse.json(
        { detail: "Authentication service timed out. Please retry." },
        {
          status: 503,
          headers: {
            "Retry-After": "5",
            "Cache-Control": "private, no-store",
          },
        },
      );
    }
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      {
        status: 502,
        headers: { "Cache-Control": "private, no-store" },
      },
    );
  }
}
