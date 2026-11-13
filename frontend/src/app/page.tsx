import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PublicHomePage } from "@/components/marketing/public-home";
import { ResponsiveWorkspaceShell } from "@/components/workspace/responsive-workspace-shell";
import { SessionServiceUnavailable } from "@/components/status/session-service-unavailable";
import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import { isValidUserIdentity } from "@/lib/auth/user-response";

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
        signal: AbortSignal.timeout(12_000),
      },
    );

    if (response.status === 401 || response.status === 403) {
      return null;
    }
    if (!response.ok) {
      // An unavailable Render instance must not appear as a logout.
      throw new Error("Aqlyra is temporarily unavailable. Please retry.");
    }

    const data =
      await readJson<UserResponse | BackendError>(
        response,
      );

    if (!isValidUserIdentity(data)) {
      // Do not disguise a malformed 200 as sign-out, or render a
      // private workspace with a missing user ID/disabled account.
      throw new Error("Backend returned an invalid user profile");
    }

    return data;
  } catch {
    // Keep HttpOnly cookies in place during a transient backend outage;
    // treat 401 as auth failure, 5xx/network errors as temporary errors.
    throw new Error("Aqlyra is temporarily unavailable. Please retry.");
  }
}

const PUBLIC_DESCRIPTION =
  "Aqlyra AI is a multilingual knowledge workspace for private document RAG, source citations, AI conversation and supported web research. Explore the public demo.";

export async function generateMetadata(): Promise<Metadata> {
  // A session can display private workspace content at this same route.
  // Never advertise the signed-in view to web crawlers.
  let hasSession: boolean;
  try {
    hasSession = Boolean(await getAccessToken());
  } catch {
    // An expired JWT plus a sleeping provider must not expose a private
    // session to crawlers or turn an outage into a redirect.
    return { robots: { index: false, follow: false } };
  }
  if (hasSession || process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY === "true") {
    return { robots: { index: false, follow: false } };
  }

  return {
    title: "Aqlyra AI — Private Document RAG & Source-Grounded Chat",
    description: PUBLIC_DESCRIPTION,
    alternates: { canonical: "https://aqlyra-ai.vercel.app/" },
    robots: { index: true, follow: true },
    openGraph: {
      type: "website",
      url: "https://aqlyra-ai.vercel.app/",
      siteName: "Aqlyra AI",
      title: "Aqlyra AI — Private Document RAG & Source-Grounded Chat",
      description: PUBLIC_DESCRIPTION,
    },
    twitter: {
      card: "summary",
      title: "Aqlyra AI — Document Search and Source-Grounded Chat",
      description: PUBLIC_DESCRIPTION,
    },
  };
}

export default async function Home() {
  let user: UserResponse | null;
  try {
    user = await getCurrentUser();
  } catch {
    return <SessionServiceUnavailable />;
  }

  if (!user) {
    // Keep existing portfolio/demo behavior. Real production exposes only
    // public marketing text to crawlers; private chat still requires login.
    if (process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY === "true") {
      redirect("/demo");
    }
    return <PublicHomePage />;
  }

  return <ResponsiveWorkspaceShell user={user} />;
}