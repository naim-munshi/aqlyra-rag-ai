import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";

export async function artifactJsonProxy(
  request: Request,
  path: string,
  method: "GET" | "POST" | "DELETE",
): Promise<Response> {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json({ detail: "Untrusted request origin" }, { status: 403 });
  }
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  let payload: string | undefined;
  if (method === "POST") {
    try {
      const raw = await request.text();
      if (raw.length > 35_000) {
        return NextResponse.json({ detail: "Request too large" }, { status: 413 });
      }
      JSON.parse(raw);
      payload = raw;
    } catch {
      return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
    }
  }
  try {
    const response = await fetch(backendUrl(path), {
      method,
      headers: {
        Authorization: "Bearer " + token,
        ...(payload === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: payload,
      cache: "no-store",
    });
    if (response.status === 204) {
      return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }
    const data = await readJson<unknown>(response);
    return NextResponse.json(data ?? { detail: "Invalid backend response" }, {
      status: response.status,
      headers: {
        ...forwardedBackendHeaders(response),
        "Cache-Control": "private, no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Artifact backend unavailable" }, { status: 502 });
  }
}

export function validArtifactId(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}
