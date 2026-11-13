import { artifactJsonProxy } from "@/lib/api/artifact-proxy";

export async function POST(request: Request) {
  return artifactJsonProxy(request, "/artifacts/render", "POST");
}
