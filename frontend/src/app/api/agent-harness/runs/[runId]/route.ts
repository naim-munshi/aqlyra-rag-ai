import { privateJsonResponse } from "@/lib/security/private-json";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { AgentApiError, AgentRunDetail } from "@/types/agent-harness";

type RouteContext = { params: Promise<{ runId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return privateJsonResponse({ detail: "Not authenticated" }, { status: 401 });
  }

  const { runId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(runId)) {
    return privateJsonResponse({ detail: "Invalid trace ID" }, { status: 400 });
  }

  try {
    const upstream = await fetch(
      backendUrl(`/agent-harness/runs/${encodeURIComponent(runId)}`),
      {
        method: "GET",
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
        signal: request.signal,
      },
    );
    const data = await readJson<AgentRunDetail | AgentApiError>(upstream);
    return privateJsonResponse(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers: forwardedBackendHeaders(upstream) },
    );
  } catch {
    return privateJsonResponse({ detail: "Unable to load agent trace" }, { status: 502 });
  }
}
