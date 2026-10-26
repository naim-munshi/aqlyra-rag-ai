import { NextResponse } from "next/server";
import { trustedProxyClientIp } from "@/lib/security/client-ip";
import { backendUrl, readJson } from "@/lib/api/backend";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (
    !body || typeof body !== "object"
    || !("email" in body)
    || typeof body.email !== "string"
  ) {
    return NextResponse.json({ detail: "Email address is required" }, { status: 400 });
  }
  try {
    const headers = new Headers({ "Content-Type": "application/json" });
    const clientIp = trustedProxyClientIp(request);
    if (clientIp) headers.set("X-Aqlyra-Client-IP", clientIp);
    const upstream = await fetch(backendUrl("/auth/request-password-reset"), {
      method: "POST",
      headers,
      body: JSON.stringify({ email: body.email }),
      cache: "no-store",
    });
    const data = await readJson(upstream);
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) responseHeaders.set("Retry-After", retryAfter);
    return NextResponse.json(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers: responseHeaders }
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" }, { status: 502 }
    );
  }
}
