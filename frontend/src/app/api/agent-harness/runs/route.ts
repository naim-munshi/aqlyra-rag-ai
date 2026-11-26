import { privateJsonResponse } from "@/lib/security/private-json";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { AgentApiError, AgentRunSummary } from "@/types/agent-harness";

export async function GET(request: Request) {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return privateJsonResponse({ detail: "Not authenticated" }, { status: 401 });
  }

  const url = new URL(request.url);
  const rawLimit = Number(url.searchParams.get("limit") ?? "20");
  const limit = Number.isFinite(rawLimit) ? Math.min(50, Math.max(1, Math.floor(rawLimit))) : 20;

  try {
    const upstream = await fetch(backendUrl(`/agent-harness/runs?limit=${limit}`), {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
      signal: request.signal,
    });
    const data = await readJson<AgentRunSummary[] | AgentApiError>(upstream);
    return privateJsonResponse(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers: forwardedBackendHeaders(upstream) },
    );
  } catch {
    return privateJsonResponse({ detail: "Unable to load agent traces" }, { status: 502 });
  }
}
