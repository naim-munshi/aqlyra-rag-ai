import { NextResponse } from "next/server";
import { artifactJsonProxy, validArtifactId } from "@/lib/api/artifact-proxy";

type Context = { params: Promise<{ artifactId: string }> };

export async function GET(request: Request, context: Context) {
  const { artifactId } = await context.params;
  if (!validArtifactId(artifactId)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  return artifactJsonProxy(request, "/artifacts/" + artifactId, "GET");
}

export async function DELETE(request: Request, context: Context) {
  const { artifactId } = await context.params;
  if (!validArtifactId(artifactId)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  return artifactJsonProxy(request, "/artifacts/" + artifactId, "DELETE");
}
