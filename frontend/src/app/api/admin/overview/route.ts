import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

const noStore = {
  "Cache-Control": "private, no-store, max-age=0",
};

export async function GET() {
  const token = await getAccessToken();

  if (!token) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401, headers: noStore },
    );
  }

  try {
    const response = await fetch(backendUrl("/admin/overview"), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (response.status === 401 || response.status === 403) {
      return NextResponse.json(
        { detail: "Not authorized" },
        { status: response.status, headers: noStore },
      );
    }
    if (!response.ok) {
      return NextResponse.json(
        { detail: "Monitoring is unavailable" },
        { status: 503, headers: noStore },
      );
    }
    return NextResponse.json(await response.json(), {
      headers: noStore,
    });
  } catch {
    return NextResponse.json(
      { detail: "Monitoring is unavailable" },
      { status: 503, headers: noStore },
    );
  }
}
