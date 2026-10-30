"use client";

import { useState } from "react";

type TrafficEntry = {
  ip: string;
  requests: number;
  visits?: number;
  chat_requests?: number;
  last_seen_utc: number;
};
type GuestTraffic = { entries: TrafficEntry[]; retention_hours: number };

export function GuestTrafficPanel() {
  const [rows, setRows] = useState<TrafficEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  async function inspect() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/admin/guest-traffic", {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("Guest traffic is unavailable or access denied");
      const data = (await response.json()) as GuestTraffic;
      setRows(Array.isArray(data.entries) ? data.entries.slice(0, 100) : []);
      setLoaded(true);
    } catch {
      setError("Unable to load private guest traffic. Admin access is required.");
      setRows([]);
      setLoaded(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-9 rounded-2xl border border-white/10 bg-[#101827] p-5"
      aria-label="Guest traffic and public IP monitoring">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Guest visitors · IP monitoring</h2>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            IPs are visible to authorized admins only, retained in Redis for
            at most 24 hours from the first event in each record; no guest
            chat text is stored here. Visits and chat requests are counts,
            not unique people.
          </p>
        </div>
        <button type="button" disabled={loading} onClick={() => void inspect()}
          className="rounded-lg border border-cyan-500/40 px-4 py-2 text-xs font-semibold text-cyan-200 disabled:opacity-50">
          {loading ? "Checking..." : "View recent guest IPs"}
        </button>
      </div>
      {error && <p role="alert" className="mt-3 text-xs text-amber-300">{error}</p>}
      {loaded && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-xs">
            <thead><tr className="border-b border-white/10 text-slate-400">
              <th className="pb-2">Public IP</th>
              <th className="pb-2">Requests</th>
              <th className="pb-2">Visits</th>
              <th className="pb-2">Chats</th>
              <th className="pb-2">Last seen (UTC)</th>
            </tr></thead>
            <tbody>{rows.map((item) => (
              <tr key={item.ip} className="border-b border-white/5">
                <td className="py-2 font-mono">{item.ip}</td>
                <td className="py-2">{item.requests}</td>
                <td className="py-2">{item.visits ?? 0}</td>
                <td className="py-2">{item.chat_requests ?? 0}</td>
                <td className="py-2">
                  {new Date(item.last_seen_utc * 1000).toISOString().replace("T", " ").slice(0, 19)}
                </td>
              </tr>
            ))}</tbody>
          </table>
          {rows.length === 0 && <p className="py-4 text-sm text-slate-400">No recent guest chat IPs.</p>}
        </div>
      )}
    </section>
  );
}
