import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const noStore = { "Cache-Control": "private, no-store, max-age=0" };

export async function GET(request: Request) {
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

  const input = new URL(request.url).searchParams;
  const limit = input.get("limit") ?? "25";
  const offset = input.get("offset") ?? "0";
  const q = input.get("q") ?? "";
  if (
    !/^[0-9]{1,2}$/.test(limit) || Number(limit) < 1 || Number(limit) > 50 ||
    !/^[0-9]{1,5}$/.test(offset) || Number(offset) > 10000 ||
    q.length > 100
  ) {
    return NextResponse.json(
      { detail: "Invalid account list filters" },
      { status: 400, headers: noStore },
    );
  }

  const params = new URLSearchParams({ limit, offset, q });
  try {
    const upstream = await fetch(
      backendUrl("/admin/users?" + params.toString()),
      {
        method: "GET",
        headers: { Authorization: "Bearer " + token },
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      },
    );
    if (upstream.status === 401 || upstream.status === 403) {
      return NextResponse.json(
        { detail: "Not authorized" },
        { status: upstream.status, headers: noStore },
      );
    }
    if (!upstream.ok) {
      return NextResponse.json(
        { detail: "Account inventory unavailable" },
        { status: 503, headers: noStore },
      );
    }
    return NextResponse.json(await upstream.json(), { headers: noStore });
  } catch {
    return NextResponse.json(
      { detail: "Account inventory unavailable" },
      { status: 503, headers: noStore },
    );
  }
}
