import { NextResponse } from "next/server";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const privateHeaders = {
  "Cache-Control": "private, no-store, max-age=0",
  "Pragma": "no-cache",
  "Vary": "Cookie",
  "X-Content-Type-Options": "nosniff",
};

// Backend owns validation/authorization. The proxy never accepts arbitrary URLs.
type Context = { params: Promise<{ path: string[] }> };
async function forward(request: Request, context: Context, method: string) {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json(
      { detail: "Cross-origin request denied" },
      { status: 403, headers: privateHeaders },
    );
  }
  let token: string | null;
  try {
    token = await getAccessToken();
  } catch {
    return NextResponse.json(
      { detail: "Session temporarily unavailable" },
      { status: 503, headers: privateHeaders },
    );
  }
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: privateHeaders },
    );
  }
  const { path } = await context.params;
  if (!path?.length || path.length > 5 ||
      path.some(part => !/^[a-zA-Z0-9_-]{1,100}$/.test(part))) {
    return NextResponse.json({ detail: "Invalid resource path" }, { status: 400, headers: privateHeaders });
  }
  let body: unknown = undefined;
  if (method === "POST" || method === "PATCH") {
    try { body = await readBoundedJson(request, 65536); }
    catch (error) {
      if (error instanceof RequestBodyTooLargeError) {
        return NextResponse.json({ detail: "Request body too large" }, { status: 413, headers: privateHeaders });
      } return NextResponse.json({ detail: "Invalid JSON" }, { status: 400, headers: privateHeaders }); }
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
      status: 204, headers: privateHeaders,
    });
    const payload = await readJson(upstream);
    if (payload === null) {
      return NextResponse.json(
        { detail: "Invalid backend response" },
        { status: 502, headers: privateHeaders },
      );
    }
    const headers = new Headers(privateHeaders);
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return NextResponse.json(payload,
      { status: upstream.status, headers });
  } catch {
    return NextResponse.json({ detail: "Study Abroad service unavailable" }, { status: 502, headers: privateHeaders });
  }
}
export const GET = (request: Request, context: Context) => forward(request, context, "GET");
export const POST = (request: Request, context: Context) => forward(request, context, "POST");
export const PATCH = (request: Request, context: Context) => forward(request, context, "PATCH");
export const DELETE = (request: Request, context: Context) => forward(request, context, "DELETE");
