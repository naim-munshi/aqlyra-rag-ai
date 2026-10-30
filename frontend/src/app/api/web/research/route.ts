import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { parseResearchRequest } from "@/lib/web/research-request";

export async function POST(request: Request) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" }, { status: 401 },
    );
  }

  let raw: unknown;
  try {
    raw = await readBoundedJson(request, 16384);
  } catch (error) {
      if (error instanceof RequestBodyTooLargeError) {
        return NextResponse.json({ detail: "Request body too large" }, { status: 413 });
      }
    return NextResponse.json(
      { detail: "Invalid JSON body" }, { status: 400 },
    );
  }
  const body = parseResearchRequest(raw);
  if (!body) {
    return NextResponse.json(
      { detail: "Invalid question, mode, source count or public URL" },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(backendUrl("/web/research"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
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
