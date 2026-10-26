import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { validArtifactId } from "@/lib/api/artifact-proxy";
import { getAccessToken } from "@/lib/auth/session";

type Context = { params: Promise<{ artifactId: string }> };

export async function GET(_request: Request, context: Context) {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  const { artifactId } = await context.params;
  if (!validArtifactId(artifactId)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  try {
    const upstream = await fetch(
      backendUrl("/artifacts/" + artifactId + "/download"),
      { headers: { Authorization: "Bearer " + token }, cache: "no-store" },
    );
    if (!upstream.ok) {
      const data = await readJson<unknown>(upstream);
      return NextResponse.json(data ?? { detail: "Download failed" }, { status: upstream.status });
    }
    const headers = new Headers({
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? "attachment",
    });
    const length = upstream.headers.get("content-length");
    if (length) headers.set("Content-Length", length);
    return new Response(upstream.body, { status: 200, headers });
  } catch {
    return NextResponse.json({ detail: "Artifact backend unavailable" }, { status: 502 });
  }
}
