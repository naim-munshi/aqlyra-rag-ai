import { NextResponse } from "next/server";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

type RouteContext = { params: Promise<{ documentId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: { "Cache-Control": "private, no-store" } },
    );
  }
  const { documentId } = await context.params;
  if (!/^[0-9a-f-]{20,64}$/i.test(documentId)) {
    return NextResponse.json({ detail: "Invalid document ID" }, { status: 400 });
  }
  const url = new URL(request.url);
  const offsetText = url.searchParams.get("offset") ?? "0";
  if (!/^(0|[1-9][0-9]*)$/.test(offsetText)) {
    return NextResponse.json({ detail: "Invalid offset" }, { status: 400 });
  }
  const offset = Number(offsetText);
  if (!Number.isSafeInteger(offset) || offset > 100000) {
    return NextResponse.json({ detail: "Offset out of range" }, { status: 400 });
  }
  try {
    const response = await fetch(
      backendUrl(
        `/documents/${encodeURIComponent(documentId)}/units?limit=30&offset=${offset}`,
      ),
      {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
        signal: request.signal,
      },
    );
    const result = await readJson(response);
    return NextResponse.json(
      result ?? { detail: "Document units unavailable" },
      {
        status: response.status,
        headers: { "Cache-Control": "private, no-store" },
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "Document preview service unavailable" },
      { status: 502, headers: { "Cache-Control": "private, no-store" } },
    );
  }
}
