import type { Metadata } from "next";

import { GuestChat } from "@/components/guest/guest-chat";

export const metadata: Metadata = {
  title: "Guest Chat | Aqlyra",
  description: "Try limited Aqlyra AI chat without signing in.",
  robots: { index: false, follow: false },
};

export default function GuestPage() {
  return <GuestChat />;
}
