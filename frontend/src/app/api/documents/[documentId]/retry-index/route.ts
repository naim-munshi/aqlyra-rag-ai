import { NextResponse } from "next/server";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type { DocumentResponse } from "@/types/document";

type Context = { params: Promise<{ documentId: string }> };

export async function POST(_request: Request, context: Context) {
  const token = await getAccessToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  const { documentId } = await context.params;
  try {
    const result = await fetch(
      backendUrl(`/documents/${encodeURIComponent(documentId)}/retry-index`),
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
    const body = await readJson<DocumentResponse | { detail?: string }>(result);
    return NextResponse.json(body ?? { detail: "Index service unavailable" }, {
      status: result.status,
    });
  } catch {
    return NextResponse.json({ detail: "Index service unreachable" }, { status: 502 });
  }
}
