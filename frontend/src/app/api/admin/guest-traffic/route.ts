import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const noStore = { "Cache-Control": "private, no-store" };

export async function GET() {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, {
      status: 401, headers: noStore,
    });
  }
  try {
    const upstream = await fetch(backendUrl("/admin/guest-traffic"), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (upstream.status === 403 || upstream.status === 401) {
      return NextResponse.json({ detail: "Not authorized" }, {
        status: upstream.status, headers: noStore,
      });
    }
    if (!upstream.ok) {
      return NextResponse.json({ detail: "Traffic unavailable" }, {
        status: 503, headers: noStore,
      });
    }
    return NextResponse.json(await upstream.json(), { headers: noStore });
  } catch {
    return NextResponse.json({ detail: "Traffic unavailable" }, {
      status: 503, headers: noStore,
    });
  }
}
