import { NextResponse } from "next/server";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";

type VoiceStatus = { available: boolean; detail: string };

export async function GET() {
  let token: string | null;
  try {
    token = await getAccessToken();
  } catch {
    // Backend refresh failure must not bubble into a 500 or clear cookies.
    return NextResponse.json(
      { available: false, detail: "Voice status is temporarily unavailable. Please retry." },
      { status: 503, headers: { "Cache-Control": "private, no-store", "Retry-After": "10" } },
    );
  }
  if (!token) {
    return NextResponse.json(
      { available: false, detail: "Sign in to use voice calls." },
      { status: 401, headers: { "Cache-Control": "private, no-store" } },
    );
  }
  try {
    const response = await fetch(backendUrl("/voice/status"), {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    const data = await readJson<VoiceStatus>(response);
    const valid = data &&
      typeof data.available === "boolean" &&
      typeof data.detail === "string";
    return NextResponse.json(
      response.ok && valid
        ? data
        : { available: false, detail: "Voice calling is unavailable. Use text chat." },
      {
        // A malformed 200 must not masquerade as a healthy voice backend.
        status: response.ok && !valid ? 502 : response.status,
        headers: {
          ...forwardedBackendHeaders(response),
          "Cache-Control": "private, no-store",
        },
      },
    );
  } catch {
    return NextResponse.json(
      { available: false, detail: "Voice calling is unavailable. Use text chat." },
      { status: 503, headers: { "Cache-Control": "private, no-store", "Retry-After": "10" } },
    );
  }
}
