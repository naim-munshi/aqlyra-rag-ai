import { redirect } from "next/navigation";

import { ArtifactWorkspace } from "@/components/artifacts/artifact-workspace";
import { Sidebar } from "@/components/workspace/sidebar";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { unauthenticatedLanding } from "@/lib/deployment/mode";
import type { UserResponse } from "@/types/auth";

async function currentUser(): Promise<UserResponse | null> {
  const token = await getAccessToken();
  if (!token) return null;
  try {
    const response = await fetch(backendUrl("/users/me"), {
      headers: { Authorization: "Bearer " + token },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const body = await readJson<UserResponse>(response);
    return body && typeof body.id === "string" ? body : null;
  } catch {
    return null;
  }
}

export default async function ArtifactsPage() {
  const user = await currentUser();
  if (!user) {
    redirect(unauthenticatedLanding(process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY));
  }
  return (
    <main className="flex min-h-screen bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <div className="hidden md:block">
        <Sidebar user={user} />
      </div>
      <div className="min-w-0 flex-1 overflow-y-auto">
        <ArtifactWorkspace />
      </div>
    </main>
  );
}
