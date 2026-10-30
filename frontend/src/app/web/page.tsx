import { redirect } from "next/navigation";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl } from "@/lib/api/backend";
import { WebResearchWorkspace } from "@/components/web/web-research-workspace";

export default async function WebPage() {
  const token = await getAccessToken();
  if (!token) redirect("/login");
  try {
    const response = await fetch(backendUrl("/users/me"), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) redirect("/login");
  } catch {
    redirect("/login");
  }
  return <WebResearchWorkspace />;
}
