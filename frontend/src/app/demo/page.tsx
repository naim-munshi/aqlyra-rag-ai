import type { Metadata } from "next";
import { DemoExperience } from "./demo-experience";

const description =
  "Explore a scripted Aqlyra demo of source-grounded RAG answers, AI conversation, citations and the platform architecture.";

export const metadata: Metadata = {
  title: "Interactive AI Knowledge Workspace Demo",
  description,
  alternates: { canonical: "https://aqlyra-ai.vercel.app/demo" },
  robots: { index: true, follow: true },
  openGraph: {
    type: "website",
    url: "https://aqlyra-ai.vercel.app/demo",
    siteName: "Aqlyra",
    title: "Aqlyra — Interactive AI Knowledge Demo",
    description,
  },
  twitter: {
    card: "summary",
    title: "Explore the Aqlyra AI Demo",
    description,
  },
};

export default function DemoPage() {
  // An explicitly requested /demo page is a public, scripted portfolio
  // walkthrough on BOTH the real app and demo-only builds.
  // Do not redirect /login or turn scripted examples into provider calls.
  return <DemoExperience />;
}
