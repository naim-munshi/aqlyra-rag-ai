import { NextResponse } from "next/server";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl, readJson } from "@/lib/api/backend";

export const dynamic = "force-dynamic";
const noStore = { "Cache-Control": "private, no-store" };

export async function POST() {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: noStore },
    );
  }

  try {
    const response = await fetch(backendUrl("/documents/cloud/recover"), {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(65000),
    });
    const data = await readJson<unknown>(response);
    return NextResponse.json(
      data ?? { detail: "Upload recovery unavailable" },
      { status: response.status, headers: noStore },
    );
  } catch {
    return NextResponse.json(
      { detail: "Upload recovery unavailable" },
      { status: 503, headers: noStore },
    );
  }
}
