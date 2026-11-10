import { redirect } from "next/navigation";

import { SessionServiceUnavailable } from "@/components/status/session-service-unavailable";
import { StudyAbroadWorkspace } from "@/components/study-abroad/study-abroad-workspace";
import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function StudyAbroadPage() {
  let token: string | null;
  try {
    token = await getAccessToken();
  } catch {
    // A cold Render instance is not evidence that the user's session expired.
    return <SessionServiceUnavailable />;
  }
  if (!token) redirect("/login");

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

  // Only real auth rejection can redirect; a 5xx is a temporary outage.
  if (response.status === 401 || response.status === 403) redirect("/login");
  if (!response.ok) return <SessionServiceUnavailable />;

  return <StudyAbroadWorkspace />;
}
