import { NextResponse } from "next/server";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";

type VoiceStatus = { available: boolean; detail: string };

export async function GET() {
  const token = await getAccessToken();
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
    });
    const data = await readJson<VoiceStatus>(response);
    return NextResponse.json(
      response.ok && data && typeof data.available === "boolean"
        ? data
        : { available: false, detail: "Voice calling is unavailable. Use text chat." },
      {
        status: response.status,
        headers: {
          ...forwardedBackendHeaders(response),
          "Cache-Control": "private, no-store",
        },
      },
    );
  } catch {
    return NextResponse.json(
      { available: false, detail: "Voice calling is unavailable. Use text chat." },
      { status: 503, headers: { "Cache-Control": "private, no-store" } },
    );
  }
}
