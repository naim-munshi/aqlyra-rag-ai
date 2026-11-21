import { notFound, redirect } from "next/navigation";
import { SessionServiceUnavailable } from "@/components/status/session-service-unavailable";
import { getAccessToken, hasRefreshToken } from "@/lib/auth/session";
import { backendUrl } from "@/lib/api/backend";
import { BrowserAgentWorkspace } from "@/components/agent/browser-agent-workspace";

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
  try {
    const response = await fetch(backendUrl("/users/me"), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    if (response.status === 401 || response.status === 403) redirect("/login");
    if (!response.ok) return <SessionServiceUnavailable />;
  } catch {
    return <SessionServiceUnavailable />;
  }
  return <BrowserAgentWorkspace />;
}
