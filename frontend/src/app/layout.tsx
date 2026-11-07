import type { Metadata, Viewport } from "next";

import { ThemeProvider } from "@/components/theme/theme-provider";

import "./globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

// The home route is account-scoped and redirects unauthenticated visitors.
// Default to noindex; only public product pages explicitly opt in.
export const metadata: Metadata = {
  metadataBase: new URL("https://aqlyra-ai.vercel.app"),
  title: {
    default: "Aqlyra | Source-Grounded AI Knowledge Workspace",
    template: "%s | Aqlyra",
  },
  description:
    "Aqlyra is an AI knowledge workspace for private document search, citation-aware answers, and research workflows.",
  applicationName: "Aqlyra",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}