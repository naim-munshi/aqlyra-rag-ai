import { privateJsonResponse } from "@/lib/security/private-json";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { AgentApiError, AgentUsageDashboard } from "@/types/agent-harness";

export async function GET(request: Request) {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return privateJsonResponse({ detail: "Not authenticated" }, { status: 401 });
  }

  const url = new URL(request.url);
  const rawDays = Number(url.searchParams.get("days") ?? "14");
  const days = Number.isFinite(rawDays) ? Math.min(31, Math.max(1, Math.floor(rawDays))) : 14;

  try {
    const upstream = await fetch(backendUrl(`/agent-harness/usage?days=${days}`), {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
      signal: request.signal,
    });
    const data = await readJson<AgentUsageDashboard | AgentApiError>(upstream);
    return privateJsonResponse(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers: forwardedBackendHeaders(upstream) },
    );
  } catch {
    return privateJsonResponse({ detail: "Unable to load daily agent usage" }, { status: 502 });
  }
}
