import { NextResponse } from "next/server";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl, readJson } from "@/lib/api/backend";

export const dynamic = "force-dynamic";
const noStore = { "Cache-Control": "private, no-store" };
type Context = { params: Promise<{ intentId: string }> };

export async function POST(_request: Request, context: Context) {
  const token = await getAccessToken();
  if (!token) return NextResponse.json(
    { detail: "Not authenticated" }, { status: 401, headers: noStore },
  );
  const { intentId } = await context.params;
  if (!/^[a-f0-9-]{36}$/.test(intentId)) return NextResponse.json(
    { detail: "Invalid upload intent" }, { status: 400, headers: noStore },
  );
  try {
    const response = await fetch(
      backendUrl(`/documents/cloud/${encodeURIComponent(intentId)}/finalize`),
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
        signal: AbortSignal.timeout(60000),
      },
    );
    const data = await readJson<unknown>(response);
    return NextResponse.json(
      data ?? { detail: "Finalization unavailable" },
      { status: response.status, headers: noStore },
    );
  } catch {
    return NextResponse.json(
      { detail: "Finalization unavailable" }, { status: 503, headers: noStore },
    );
  }
}
