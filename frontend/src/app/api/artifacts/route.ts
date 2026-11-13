import { artifactJsonProxy } from "@/lib/api/artifact-proxy";

export async function GET(request: Request) {
  return artifactJsonProxy(request, "/artifacts", "GET");
}
