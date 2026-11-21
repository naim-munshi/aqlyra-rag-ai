import { redirect } from "next/navigation";

import { SessionServiceUnavailable } from "@/components/status/session-service-unavailable";
import { BrowserAgentWorkspace } from "@/components/agent/browser-agent-workspace";
import { backendUrl } from "@/lib/api/backend";
import { getAccessToken, hasRefreshToken } from "@/lib/auth/session";

export default async function BrowserAgentPage() {
  let token: string | null;
  try {
    token = await getAccessToken({ allowRefresh: false });
  } catch {
    return <SessionServiceUnavailable />;
  }

  if (!token) {
    if (await hasRefreshToken()) return <SessionServiceUnavailable />;
    redirect("/login");
  }

  let response: Response;
  try {
    response = await fetch(backendUrl("/users/me"), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
  } catch {
    return <SessionServiceUnavailable />;
  }

  if (response.status === 401 || response.status === 403) redirect("/login");
  if (!response.ok) return <SessionServiceUnavailable />;

  return <BrowserAgentWorkspace />;
}
