import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

// Backend owns validation/authorization. The proxy never accepts arbitrary URLs.
type Context = { params: Promise<{ path: string[] }> };
async function forward(request: Request, context: Context, method: string) {
  const token = await getAccessToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const { path } = await context.params;
  if (!path?.length || path.length > 5 ||
      path.some(part => !/^[a-zA-Z0-9_-]{1,100}$/.test(part))) {
    return NextResponse.json({ detail: "Invalid resource path" }, { status: 400 });
  }
  let body: unknown = undefined;
  if (method === "POST" || method === "PATCH") {
    try { body = await readBoundedJson(request, 65536); }
    catch (error) {
      if (error instanceof RequestBodyTooLargeError) {
        return NextResponse.json({ detail: "Request body too large" }, { status: 413 });
      } return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 }); }
  }
  try {
    const upstream = await fetch(
      backendUrl("/study-abroad/" + path.map(encodeURIComponent).join("/")),
      {
        method, headers: {
          Authorization: `Bearer ${token}`,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        cache: "no-store", signal: request.signal,
      },
    );
    if (upstream.status === 204) return new NextResponse(null, {
      status: 204, headers: { "Cache-Control": "no-store" },
    });
    const payload = await readJson(upstream);
    const headers = new Headers({ "Cache-Control": "no-store" });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return NextResponse.json(payload ?? { detail: "Invalid upstream response" },
      { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ detail: "Study Abroad service unavailable" }, { status: 502 });
  }
}
export const GET = (request: Request, context: Context) => forward(request, context, "GET");
export const POST = (request: Request, context: Context) => forward(request, context, "POST");
export const PATCH = (request: Request, context: Context) => forward(request, context, "PATCH");
export const DELETE = (request: Request, context: Context) => forward(request, context, "DELETE");
