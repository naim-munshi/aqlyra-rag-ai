import { redirect } from "next/navigation";

import { ResponsiveWorkspaceShell } from "@/components/workspace/responsive-workspace-shell";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { unauthenticatedLanding } from "@/lib/deployment/mode";
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
    // Portfolio-only builds redirect to the interactive preview, while the
    // actual software takes unauthenticated visitors to real account sign-in.
    redirect(unauthenticatedLanding(process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY));
  }

  return <ResponsiveWorkspaceShell user={user} />;
}