import { redirect } from "next/navigation";

import { ResponsiveWorkspaceShell } from "@/components/workspace/responsive-workspace-shell";
import { SessionServiceUnavailable } from "@/components/status/session-service-unavailable";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken, hasRefreshToken } from "@/lib/auth/session";
import { unauthenticatedLanding } from "@/lib/deployment/mode";
import type {
  BackendError,
  UserResponse,
} from "@/types/auth";

async function getCurrentUser(): Promise<UserResponse | null> {
  const token = await getAccessToken({ allowRefresh: false });

  if (!token) {
    if (await hasRefreshToken()) {
      throw new Error("Session renewal required");
    }
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
        signal: AbortSignal.timeout(12_000),
      },
    );

    if (response.status === 401 || response.status === 403) {
      return null;
    }
    if (!response.ok) {
      throw new Error("Aqlyra is temporarily unavailable");
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
    throw new Error("Aqlyra is temporarily unavailable");
  }
}

export default async function Home() {
  let user: UserResponse | null;
  try {
    user = await getCurrentUser();
  } catch {
    return <SessionServiceUnavailable />;
  }

  if (!user) {
    // Portfolio-only builds redirect to the interactive preview, while the
    // actual software takes unauthenticated visitors to real account sign-in.
    redirect(unauthenticatedLanding(process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY));
  }

  return <ResponsiveWorkspaceShell user={user} />;
}