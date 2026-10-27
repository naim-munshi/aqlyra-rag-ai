"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, Database, FileText, RefreshCcw, Shield, Users } from "lucide-react";
import type { AdminOverview } from "@/types/admin";

const integer = new Intl.NumberFormat("en-US");

function StatCard({ label, value, description }: { label: string; value: string; description: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#101827] p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-2 text-xs text-slate-400">{description}</p>
    </div>
  );
}

export function AdminMonitor({ initialData }: { initialData: AdminOverview }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [warning, setWarning] = useState("");
  const [authorized, setAuthorized] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/admin/overview", {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (response.status === 401 || response.status === 403) {
        setAuthorized(false);
        setWarning("Your administrator session is not authorized.");
        return;
      }
      if (!response.ok) throw new Error("Metrics unavailable");
      const payload = (await response.json()) as AdminOverview;
      setData(payload);
      setWarning("");
    } catch {
      setWarning("Metrics could not be refreshed. Showing last successfully received sample.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const maxSignups = Math.max(1, ...data.users.signups_last_7_days.map((x) => x.count));

  if (!authorized) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080b12] p-6 text-slate-200">
        <div className="max-w-sm rounded-2xl border border-white/10 p-6">
          <Shield aria-hidden="true" className="mb-4 text-amber-300" />
          <p role="alert">{warning}</p>
          <Link href="/" className="mt-4 inline-block text-cyan-300">Return to workspace</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#080b12] px-5 py-8 text-slate-100 md:px-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-300">
              <ArrowLeft size={16} aria-hidden="true" /> Back to Aqlyra
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <span className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-cyan-300"><Activity size={24} aria-hidden="true" /></span>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Admin monitoring</h1>
                <p className="mt-1 text-sm text-slate-400">Private, aggregated operational statistics</p>
              </div>
            </div>
          </div>
          <button type="button" disabled={loading} onClick={() => void refresh()}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-50">
            <RefreshCcw size={15} aria-hidden="true" /> {loading ? "Refreshing…" : "Refresh"}
          </button>
        </header>

        <div className="mt-6 rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-4 py-3 text-sm text-slate-300" role="status">
          API traffic below is collected <strong>per backend process, since its last restart</strong>. It is not unique website visitors,
          device analytics, geographically identified traffic, or cross-server totals.
          The account statistics come from PostgreSQL.
        </div>
        {warning && <p className="mt-4 rounded-xl border border-amber-500/30 p-3 text-sm text-amber-200" role="alert">{warning}</p>}

        <section className="mt-7" aria-label="Traffic overview">
          <div className="mb-4 flex items-center gap-2"><Activity size={18} className="text-cyan-300" /><h2 className="text-lg font-semibold">API traffic</h2></div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="API requests" value={integer.format(data.traffic.request_total)} description="Per process since restart" />
            <StatCard label="Server errors (5xx)" value={integer.format(data.traffic.server_errors)} description={`${data.traffic.server_error_percent}% of API requests`} />
            <StatCard label="Avg. latency" value={`${data.traffic.average_latency_ms.toFixed(1)} ms`} description="Arithmetic mean, not p95" />
            <StatCard label="Rate-limit hits" value={integer.format(data.traffic.rate_limit_exceeded)} description="Requests rejected by limits" />
          </div>
        </section>

        <section className="mt-9" aria-label="Account overview">
          <div className="mb-4 flex items-center gap-2"><Users size={18} className="text-cyan-300" /><h2 className="text-lg font-semibold">Users and content</h2></div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Registered accounts" value={integer.format(data.users.registered_total)} description="All registered users" />
            <StatCard label="Enabled accounts" value={integer.format(data.users.active_accounts)} description="Not equivalent to online users" />
            <StatCard label="Verified accounts" value={integer.format(data.users.verified_accounts)} description="Verified identities" />
            <StatCard label="User documents" value={integer.format(data.users.documents_total)} description="Stored metadata records" />
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <Database size={14} aria-hidden="true" /> Conversations: {integer.format(data.users.conversations_total)}
            <span className="mx-2">·</span>
            <FileText size={14} aria-hidden="true" /> HTTP 4xx responses: {integer.format(data.traffic.client_errors)}
          </div>
        </section>

        <section className="mt-9" aria-label="Cloud object storage lifecycle">
          <div className="mb-4 flex items-center gap-2">
            <Database size={18} className="text-cyan-300" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Cloud storage integrity</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Claimed uploads" value={integer.format(data.cloud_storage.claimed)} description="May include active verification" />
            <StatCard label="Stale claims" value={integer.format(data.cloud_storage.stale_claimed)} description="Claimed more than 5 min ago; review" />
            <StatCard label="Staging cleanup" value={integer.format(data.cloud_storage.cleanup_candidates)} description="Expired candidates after 24h grace" />
            <StatCard label="Failed intents" value={integer.format(data.cloud_storage.failed_intents)} description="Operator review; not auto-deleted" />
          </div>
          <p className="mt-3 text-xs text-slate-400">
            Database aggregate counts, not inspected remote objects. Cleanup and
            recovery require explicit operator approval; no automatic deletion.
          </p>
        </section>

        <div className="mt-9 grid gap-5 lg:grid-cols-2">
          <section className="rounded-2xl border border-white/10 bg-[#101827] p-5" aria-labelledby="signup-title">
            <h2 id="signup-title" className="font-semibold">New users · last 7 days</h2>
            <p className="mt-1 text-xs text-slate-400">UTC dates, based on account registration</p>
            <div className="mt-6 flex h-44 items-end justify-between gap-2">
              {data.users.signups_last_7_days.map((day) => (
                <div className="flex min-w-0 flex-1 flex-col items-center gap-2" key={day.date}>
                  <span className="text-xs tabular-nums text-slate-300">{day.count}</span>
                  <div role="img" aria-label={`${day.date}: ${day.count} registrations`}
                    className="w-full max-w-12 rounded-t-md bg-cyan-400/80"
                    style={{ height: `${Math.max(3, (day.count / maxSignups) * 118)}px` }} />
                  <span className="text-[10px] text-slate-500">{day.date.slice(5)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-white/10 bg-[#101827] p-5" aria-labelledby="routes-title">
            <h2 id="routes-title" className="font-semibold">Most requested API routes</h2>
            <p className="mt-1 text-xs text-slate-400">Route templates only; no queries, IPs or document identifiers</p>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[360px] text-left text-xs">
                <thead className="border-b border-white/10 text-slate-400">
                  <tr><th className="pb-3 pr-3">Method</th><th className="pb-3">Route</th><th className="pb-3 text-right">Requests</th><th className="pb-3 text-right">5xx</th></tr>
                </thead>
                <tbody>
                  {data.traffic.routes.map((entry) => (
                    <tr key={`${entry.method}:${entry.route}`} className="border-b border-white/5">
                      <td className="py-3 pr-3 font-mono text-cyan-300">{entry.method}</td>
                      <td className="max-w-[220px] break-all py-3 font-mono text-slate-300">{entry.route}</td>
                      <td className="py-3 text-right tabular-nums">{entry.requests}</td>
                      <td className="py-3 text-right tabular-nums">{entry.server_errors}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.traffic.routes.length === 0 && <p className="py-6 text-sm text-slate-400">No API requests recorded yet.</p>}
            </div>
          </section>
        </div>
        <footer className="mt-8 text-xs text-slate-500">
          Sample collected {data.generated_at.replace("T", " ").slice(0, 19)} UTC · uptime {integer.format(data.traffic.uptime_seconds)}s.
          Auto-refresh every 60 seconds while visible. No individual browsing histories are collected.
        </footer>
      </div>
    </main>
  );
}
