import { NextResponse } from "next/server";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl, readJson } from "@/lib/api/backend";

export async function POST(request: Request) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  let body: unknown;
  try { body = await request.json(); } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ detail: "Invalid approval" }, { status: 400 });
  }
  const fields = body as Record<string, unknown>;
  if (
    fields.approved !== true ||
    typeof fields.plan_token !== "string" ||
    fields.plan_token.length < 20 ||
    fields.plan_token.length > 4096
  ) {
    return NextResponse.json({ detail: "Explicit approval is required" }, { status: 400 });
  }
  try {
    const response = await fetch(backendUrl("/agent/browser/execute"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ approved: true, plan_token: fields.plan_token }),
      cache: "no-store",
      signal: request.signal,
    });
    const data = await readJson(response);
    return NextResponse.json(
      data ?? { detail: "Invalid browser execution response" },
      { status: response.status, headers: { "Cache-Control": "private, no-store" } },
    );
  } catch {
    return NextResponse.json(
      { detail: "Browser agent backend unavailable" }, { status: 502 },
    );
  }
}
