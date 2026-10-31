import type { Metadata } from "next";
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
  // An explicitly requested /demo page is a public, scripted portfolio
  // walkthrough on BOTH the real app and demo-only builds.
  // Do not redirect /login or turn scripted examples into provider calls.
  return <DemoExperience />;
}
