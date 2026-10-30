import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl, readJson } from "@/lib/api/backend";

export async function POST(request: Request) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  let body: unknown;
  try { body = await readBoundedJson(request, 8192); } catch (error) {
      if (error instanceof RequestBodyTooLargeError) {
        return NextResponse.json({ detail: "Request body too large" }, { status: 413 });
      }
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ detail: "Invalid plan" }, { status: 400 });
  }
  const fields = body as Record<string, unknown>;
  if (
    typeof fields.task !== "string" ||
    fields.task.length < 5 || fields.task.length > 500 ||
    typeof fields.start_url !== "string" ||
    fields.start_url.length < 12 || fields.start_url.length > 2048
  ) {
    return NextResponse.json({ detail: "Task and start URL are required" }, { status: 400 });
  }
  try {
    const response = await fetch(backendUrl("/agent/browser/plan"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        task: fields.task, start_url: fields.start_url,
      }),
      cache: "no-store",
      signal: request.signal,
    });
    const data = await readJson(response);
    return NextResponse.json(
      data ?? { detail: "Invalid browser planning response" },
      { status: response.status, headers: { "Cache-Control": "private, no-store" } },
    );
  } catch {
    return NextResponse.json(
      { detail: "Browser agent backend unavailable" }, { status: 502 },
    );
  }
}
