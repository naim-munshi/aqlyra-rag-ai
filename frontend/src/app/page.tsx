import { redirect } from "next/navigation";

import { KnowledgeWorkspace } from "@/components/workspace/knowledge-workspace";
import { Sidebar } from "@/components/workspace/sidebar";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type {
  BackendError,
  UserResponse,
} from "@/types/auth";

async function getCurrentUser(): Promise<UserResponse | null> {
  const token = await getAccessToken();

  if (!token) {
    return null;
  }

  try {
    const response = await fetch(
      backendUrl("/users/me"),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const data =
      await readJson<UserResponse | BackendError>(
        response,
      );

    if (
      !data ||
      !("username" in data)
    ) {
      return null;
    }

    return data;
  } catch {
    return null;
  }
}

export default async function Home() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <main className="flex h-screen overflow-hidden bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <Sidebar user={user} />
      <KnowledgeWorkspace user={user} />
    </main>
  );
}