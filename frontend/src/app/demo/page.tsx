import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DemoExperience } from "./demo-experience";

export const metadata: Metadata = {
  title: "Explore Aqlyra | AI Knowledge Workspace Demo",
  description:
    "Interactive Aqlyra portfolio preview: explore source-grounded RAG " +
    "examples, conversation workflows, and the engineering architecture.",
  robots: {
    index: true,
    follow: true,
  },
};

export default function DemoPage() {
  // Production has real auth and must never route users to a scripted preview.
  // Keep this experience only for explicitly configured portfolio builds.
  if (process.env.NEXT_PUBLIC_AQLYRA_DEMO_ONLY !== "true") {
    redirect("/login");
  }
  return <DemoExperience />;
}
