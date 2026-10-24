import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

export async function POST(request: Request) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" }, { status: 401 },
    );
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Invalid JSON body" }, { status: 400 },
    );
  }
  if (
    !body || typeof body !== "object"
    || !("question" in body)
    || typeof body.question !== "string"
    || body.question.trim().length < 3
    || body.question.length > 600
  ) {
    return NextResponse.json(
      { detail: "Question must be between 3 and 600 characters" },
      { status: 400 },
    );
  }
  const maxSources = (
    "max_sources" in body && typeof body.max_sources === "number"
  ) ? body.max_sources : 4;
  if (!Number.isInteger(maxSources) || maxSources < 1 || maxSources > 5) {
    return NextResponse.json(
      { detail: "max_sources must be between 1 and 5" }, { status: 400 },
    );
  }
  try {
    const upstream = await fetch(backendUrl("/web/research"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        question: body.question.trim(),
        max_sources: maxSources,
      }),
      cache: "no-store",
      signal: request.signal,
    });
    const payload = await readJson(upstream);
    const headers = new Headers({ "Cache-Control": "no-store" });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return NextResponse.json(
      payload ?? { detail: "Invalid backend response" },
      { status: upstream.status, headers },
    );
  } catch {
    return NextResponse.json(
      { detail: "Web research backend unavailable" }, { status: 502 },
    );
  }
}
