import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearEmailVerificationToken,
  setEmailVerificationToken,
} from "@/lib/auth/session";
import type {
  BackendError,
  ResendVerificationInput,
  VerificationDispatchResponse,
} from "@/types/auth";

export async function POST(request: Request) {
  let body: ResendVerificationInput;

  try {
    body = (await request.json()) as ResendVerificationInput;
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
      backendUrl("/auth/resend-verification"),
      {
        method: "POST",
        headers: backendHeaders,
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );
    const data =
      await readJson<
        VerificationDispatchResponse | BackendError
      >(response);
    const retryAfter = response.headers.get("retry-after");
    const responseHeaders = new Headers();

    if (retryAfter) {
      responseHeaders.set("Retry-After", retryAfter);
    }

    if (
      response.ok &&
      data &&
      "verification_token" in data
    ) {
      const {
        verification_token: verificationToken,
        ...browserData
      } = data;

      if (verificationToken) {
        await setEmailVerificationToken(verificationToken);
      } else {
        await clearEmailVerificationToken();
      }

      return NextResponse.json(browserData, {
        status: response.status,
        headers: responseHeaders,
      });
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
