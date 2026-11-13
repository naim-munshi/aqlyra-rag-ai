import { redirect } from "next/navigation";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl } from "@/lib/api/backend";
import { BrowserAgentWorkspace } from "@/components/agent/browser-agent-workspace";

export default async function BrowserAgentPage() {
  const token = await getAccessToken();
  if (!token) redirect("/login");
  try {
    const response = await fetch(backendUrl("/users/me"), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) redirect("/login");
  } catch {
    redirect("/login");
  }
  return <BrowserAgentWorkspace />;
}
