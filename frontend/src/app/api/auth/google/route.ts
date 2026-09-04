import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import { completeAuthentication } from "@/lib/auth/complete-authentication";
import type { GoogleCredentialInput } from "@/types/auth";

export async function POST(request: Request) {
  let body: GoogleCredentialInput;

  try {
    body = (await request.json()) as GoogleCredentialInput;
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

  try {
    const response = await fetch(
      backendUrl("/auth/google"),
      {
        method: "POST",
        headers: backendHeaders,
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    return await completeAuthentication(
      response,
      "Google sign-in failed",
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" },
      { status: 502 },
    );
  }
}
