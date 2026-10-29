import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

import { trustedProxyClientIp } from "@/lib/security/client-ip";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearEmailVerificationToken,
  setEmailVerificationToken,
} from "@/lib/auth/session";
import type {
  BackendError,
  BackendRegistrationResponse,
  RegisterInput,
} from "@/types/auth";

export async function POST(request: Request) {
  let body: RegisterInput;

  try {
    body = (await readBoundedJson(request)) as RegisterInput;
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
      await readJson<BackendRegistrationResponse | BackendError>(
        response,
      );

    const retryAfter =
      response.headers.get("retry-after");

    const responseHeaders = new Headers();

    if (retryAfter) {
      responseHeaders.set(
        "Retry-After",
        retryAfter,
      );
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
