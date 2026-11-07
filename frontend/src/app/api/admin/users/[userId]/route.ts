import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const noStore = { "Cache-Control": "private, no-store, max-age=0" };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type RouteContext = { params: Promise<{ userId: string }> };

async function proxyMutation(request: Request, context: RouteContext, method: "PATCH" | "DELETE") {
  // The root Next.js proxy also enforces origin, but sensitive mutations
  // independently check it so an accidental route-matcher change fails closed.
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json(
      { detail: "Cross-origin request denied" },
      { status: 403, headers: noStore },
    );
  }

  const { userId } = await context.params;
  if (!uuid.test(userId)) {
    return NextResponse.json(
      { detail: "Invalid account ID" },
      { status: 400, headers: noStore },
    );
  }

  let token: string | null;
  try {
    token = await getAccessToken();
  } catch {
    return NextResponse.json(
      { detail: "Session unavailable" },
      { status: 503, headers: noStore },
    );
  }
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: noStore },
    );
  }

  let payload: unknown;
  try {
    // Enforce the byte cap during streaming, before any complete-body allocation.
    // This also handles forged/missing Content-Length and multi-byte UTF-8.
    payload = await readBoundedJson(request, 2048);
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return NextResponse.json(
        { detail: "Request too large" },
        { status: 413, headers: noStore },
      );
    }
    return NextResponse.json(
      { detail: "Invalid account mutation body" },
      { status: 400, headers: noStore },
    );
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return NextResponse.json(
      { detail: "Invalid account mutation body" },
      { status: 400, headers: noStore },
    );
  }

  const target = payload as Record<string, unknown>;
  if (
    typeof target.confirm_email !== "string" ||
    target.confirm_email.length > 254 ||
    (method === "PATCH" && target.action !== "disable" && target.action !== "enable") ||
    (method === "DELETE" && target.confirmation !== "DELETE ACCOUNT")
  ) {
    return NextResponse.json(
      { detail: "Invalid account confirmation" },
      { status: 400, headers: noStore },
    );
  }

  const path =
    method === "PATCH"
      ? "/admin/users/" + userId + "/status"
      : "/admin/users/" + userId;
  try {
    const upstream = await fetch(backendUrl(path), {
      method,
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if ([401, 403, 404, 409, 422].includes(upstream.status)) {
      const result = await upstream.json().catch(() => null);
      const detail = typeof result?.detail === "string" ? result.detail : "Action rejected";
      return NextResponse.json(
        { detail },
        { status: upstream.status, headers: noStore },
      );
    }
    if (!upstream.ok) {
      return NextResponse.json(
        { detail: "Account action unavailable" },
        { status: 503, headers: noStore },
      );
    }
    return NextResponse.json(await upstream.json(), { headers: noStore });
  } catch {
    return NextResponse.json(
      { detail: "Account action unavailable" },
      { status: 503, headers: noStore },
    );
  }
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxyMutation(request, context, "PATCH");
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxyMutation(request, context, "DELETE");
}
