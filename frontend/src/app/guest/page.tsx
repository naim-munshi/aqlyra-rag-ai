import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { GuestChat } from "@/components/guest/guest-chat";

export const metadata: Metadata = {
  title: "Guest Chat | Aqlyra",
  description: "Try limited Aqlyra AI chat without signing in.",
  robots: { index: false, follow: false },
};

export default function GuestPage() {
  if (process.env.NEXT_PUBLIC_AQLYRA_GUEST_ENABLED !== "true") {
    redirect("/login");
  }
  return <GuestChat />;
}
