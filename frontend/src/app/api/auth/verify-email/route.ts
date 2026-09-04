import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import { completeAuthentication } from "@/lib/auth/complete-authentication";
import { getEmailVerificationToken } from "@/lib/auth/session";
import type { VerifyEmailInput } from "@/types/auth";

export async function POST(request: Request) {
  let body: VerifyEmailInput;

  try {
    body = (await request.json()) as VerifyEmailInput;
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
    backendHeaders.set("X-Aqlyra-Client-IP", clientIp);
  }

  const verificationToken =
    await getEmailVerificationToken();

  if (!verificationToken) {
    return NextResponse.json(
      { detail: "Request a new verification code first" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(
      backendUrl("/auth/verify-email"),
      {
        method: "POST",
        headers: backendHeaders,
        body: JSON.stringify({
          code: body.code,
          verification_token: verificationToken,
        }),
        cache: "no-store",
      },
    );

    return await completeAuthentication(
      response,
      "Email verification failed",
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}
