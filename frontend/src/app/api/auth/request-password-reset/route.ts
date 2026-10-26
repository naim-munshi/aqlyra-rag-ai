import { NextResponse } from "next/server";
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
    const upstream = await fetch(backendUrl("/auth/request-password-reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email }),
      cache: "no-store",
    });
    const data = await readJson(upstream);
    const headers = new Headers({ "Cache-Control": "no-store" });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return NextResponse.json(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers }
    );
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable" }, { status: 502 }
    );
  }
}
