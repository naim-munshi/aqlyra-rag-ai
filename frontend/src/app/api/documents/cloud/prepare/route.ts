import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl, readJson } from "@/lib/api/backend";

export const dynamic = "force-dynamic";
const noStore = { "Cache-Control": "private, no-store" };

export async function POST(request: NextRequest) {
  const token = await getAccessToken();
  if (!token) return NextResponse.json(
    { detail: "Not authenticated" }, { status: 401, headers: noStore },
  );
  if (Number(request.headers.get("content-length") || 0) > 4096) {
    return NextResponse.json(
      { detail: "Upload manifest too large" }, { status: 413, headers: noStore },
    );
  }
  let manifest: unknown;
  try {
    manifest = await request.json();
  } catch {
    return NextResponse.json(
      { detail: "Invalid manifest" }, { status: 400, headers: noStore },
    );
  }
  try {
    const response = await fetch(backendUrl("/documents/cloud/prepare"), {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(manifest),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    const data = await readJson<unknown>(response);
    return NextResponse.json(
      data ?? { detail: "Upload service unavailable" },
      { status: response.status, headers: noStore },
    );
  } catch {
    return NextResponse.json(
      { detail: "Upload service unavailable" }, { status: 503, headers: noStore },
    );
  }
}
