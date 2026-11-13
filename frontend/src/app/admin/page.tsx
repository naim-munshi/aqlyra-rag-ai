import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AdminMonitor } from "@/components/admin/admin-monitor";
import { backendUrl } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type { AdminOverview } from "@/types/admin";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Operations | Aqlyra",
  robots: { index: false, follow: false },
};

export default async function AdminPage() {
  const token = await getAccessToken();
  if (!token) redirect("/login");

  let response: Response;
  try {
    response = await fetch(backendUrl("/admin/overview"), {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080b12] p-6 text-white">
        <p role="status">Monitoring service is currently unavailable.</p>
      </main>
    );
  }
  if (response.status === 401) redirect("/login");
  if (response.status === 403) notFound();
  if (!response.ok) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080b12] p-6 text-white">
        <p role="status">Monitoring service is currently unavailable.</p>
      </main>
    );
  }
  const overview = (await response.json()) as AdminOverview;
  return <AdminMonitor initialData={overview} />;
}
