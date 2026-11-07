import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PublicHomePage } from "@/components/marketing/public-home";
import { ResponsiveWorkspaceShell } from "@/components/workspace/responsive-workspace-shell";
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

    if (
      !data ||
      !("username" in data)
    ) {
      return null;
    }

    return data;
  } catch {
    // Keep HttpOnly cookies in place during a transient backend outage;
    // treat 401 as auth failure, 5xx/network errors as temporary errors.
    throw new Error("Aqlyra is temporarily unavailable. Please retry.");
  }
}

const PUBLIC_DESCRIPTION =
  "Meet Aqlyra AI: chat with AI, ask questions about private documents, explore source-grounded RAG answers and research tools.";

export async function generateMetadata(): Promise<Metadata> {
  // A session can display private workspace content at this same route.
  // Never advertise the signed-in view to web crawlers.
  const hasSession = Boolean(await getAccessToken());
  if (hasSession || process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY === "true") {
    return { robots: { index: false, follow: false } };
  }

  return {
    title: "Aqlyra AI — Chat, Document Search and Grounded Answers",
    description: PUBLIC_DESCRIPTION,
    alternates: { canonical: "https://aqlyra-ai.vercel.app/" },
    robots: { index: true, follow: true },
    openGraph: {
      type: "website",
      url: "https://aqlyra-ai.vercel.app/",
      siteName: "Aqlyra",
      title: "Aqlyra AI — Chat, Search and Explore",
      description: PUBLIC_DESCRIPTION,
    },
    twitter: {
      card: "summary",
      title: "Aqlyra AI — Private Knowledge and AI Chat",
      description: PUBLIC_DESCRIPTION,
    },
  };
}

export default async function Home() {
  const user = await getCurrentUser();

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