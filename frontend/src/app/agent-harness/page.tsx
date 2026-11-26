"use client";

import { useEffect, useState } from "react";

import type {
  AgentApiError,
  AgentRunDetail,
  AgentRunSummary,
  AgentUsageDashboard,
} from "@/types/agent-harness";

function formatCost(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(value);
}

function formatDuration(value: number) {
  if (value < 1_000) return `${value} ms`;
  return `${(value / 1_000).toFixed(2)} s`;
}

function messageFrom(data: AgentApiError | null, fallback: string) {
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail && !Array.isArray(data.detail)) {
    return data.detail.message ?? fallback;
  }
  return fallback;
}

function labelForStep(stepType: string) {
  return stepType.replaceAll("_", " ").replace(/\b\w/g, (value) => value.toUpperCase());
}

function summaryText(value: Record<string, unknown>) {
  const entries = Object.entries(value);
  if (!entries.length) return "No additional metadata";
  return entries.map(([key, item]) => {
    const rendered = Array.isArray(item)
      ? item.join(", ")
      : typeof item === "object" && item !== null
        ? JSON.stringify(item)
        : String(item);
    return `${key.replaceAll("_", " ")}: ${rendered}`;
  }).join(" · ");
}

export default function AgentHarnessPage() {
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [usage, setUsage] = useState<AgentUsageDashboard | null>(null);
  const [selected, setSelected] = useState<AgentRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadUsage() {
    try {
      const response = await fetch("/api/agent-harness/usage?days=14", {
        cache: "no-store",
      });
      const data = await response.json() as AgentUsageDashboard | AgentApiError;
      if (response.ok && "daily_usage" in data) {
        setUsage(data);
      }
    } catch {
      // The run list remains useful when the daily roll-up is unavailable.
    }
  }

  async function loadRuns() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/agent-harness/runs?limit=50", {
        cache: "no-store",
      });
      const data = await response.json() as AgentRunSummary[] | AgentApiError;
      if (!response.ok || !Array.isArray(data)) {
        setError(messageFrom(data as AgentApiError, "Unable to load traces."));
        return;
      }
      setRuns(data);
      if (selected) {
        const refreshed = data.find((item) => item.id === selected.id);
        if (!refreshed) setSelected(null);
      }
    } catch {
      setError("Trace service is unavailable.");
    } finally {
      setLoading(false);
    }
  }

  async function openRun(runId: string) {
    setDetailLoading(true);
    setError("");
    try {
      const response = await fetch(
        `/api/agent-harness/runs/${encodeURIComponent(runId)}`,
        { cache: "no-store" },
      );
      const data = await response.json() as AgentRunDetail | AgentApiError;
      if (!response.ok || !("steps" in data)) {
        setError(messageFrom(data as AgentApiError, "Unable to load trace detail."));
        return;
      }
      setSelected(data);
    } catch {
      setError("Trace detail is unavailable.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    // Defer initial network loading until after the effect commit.
    const timer = window.setTimeout(() => {
      void loadRuns();
      void loadUsage();
    }, 0);
    // This page is an on-demand trace viewer; no background polling.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-600">
            Knowledge observability
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            Research agent traces
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Review each research run, the retrieval tools it used, citation outcome,
            latency and estimated language-model cost. Only your own traces are shown.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void loadRuns();
            void loadUsage();
          }}
          disabled={loading}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {usage && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Daily agent spend</h2>
              <p className="mt-1 text-xs text-slate-500">
                Completed runs by UTC date · generation-token estimate only
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 px-3 py-2">
              <p className="text-[11px] text-slate-500">Daily budget</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {formatCost(usage.daily_budget_usd)}
              </p>
            </div>
          </div>
          {usage.daily_usage.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No completed runs in the last 14 UTC days.</p>
          ) : (
            <div className="mt-5 space-y-3">
              {[...usage.daily_usage].reverse().map((day) => {
                const ratio = usage.daily_budget_usd > 0
                  ? Math.min(100, (day.cost_usd / usage.daily_budget_usd) * 100)
                  : 0;
                return (
                  <div
                    key={day.usage_date}
                    className="grid grid-cols-[76px_minmax(0,1fr)_92px] items-center gap-3"
                  >
                    <span className="text-[11px] text-slate-500">
                      {new Date(day.usage_date + "T00:00:00Z").toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        timeZone: "UTC",
                      })}
                    </span>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-sky-600"
                        style={{ width: ratio + "%" }}
                      />
                    </div>
                    <span className="text-right text-xs font-medium text-slate-700">
                      {formatCost(day.cost_usd)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          <p className="mt-4 text-[11px] leading-5 text-slate-500">
            Embedding, query-rewrite, reranker and grounding-verifier charges are not itemized in this estimate.
          </p>
        </section>
      )}

      <div className="grid min-h-[560px] gap-5 lg:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.6fr)]">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-900">Recent runs</h2>
            <p className="mt-1 text-xs text-slate-500">{runs.length} trace(s)</p>
          </div>
          {loading && runs.length === 0 ? (
            <div className="p-5 text-sm text-slate-500">Loading traces…</div>
          ) : runs.length === 0 ? (
            <div className="p-5 text-sm leading-6 text-slate-500">
              No research-agent runs yet. Enable the agent in Knowledge mode after its
              provider prices and daily budget are configured.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {runs.map((run) => (
                <li key={run.id}>
                  <button
                    type="button"
                    onClick={() => void openRun(run.id)}
                    className={[
                      "w-full px-4 py-4 text-left transition hover:bg-slate-50",
                      selected?.id === run.id ? "bg-sky-50" : "",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="line-clamp-1 text-sm font-medium text-slate-900">
                        {run.question_redacted}
                      </span>
                      <span className={[
                        "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                        run.status === "completed" ? "bg-emerald-50 text-emerald-700" :
                          run.status === "refused" ? "bg-amber-50 text-amber-800" :
                            run.status === "failed" ? "bg-rose-50 text-rose-700" :
                              "bg-slate-100 text-slate-600",
                      ].join(" ")}>
                        {run.status}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span>{formatCost(run.cost_usd)}</span>
                      <span>{run.input_tokens + run.output_tokens} tokens</span>
                      <span>{formatDuration(run.latency_ms)}</span>
                    </div>
                    <p className="mt-2 text-[10px] text-slate-400">
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="min-w-0 rounded-2xl border border-slate-200 bg-white shadow-sm">
          {!selected ? (
            <div className="flex min-h-[400px] items-center justify-center px-6 text-center">
              <div>
                <div className="text-sm font-semibold text-slate-800">
                  {detailLoading ? "Loading trace…" : "Select a research run"}
                </div>
                <p className="mt-2 text-sm text-slate-500">
                  Step-level tool calls, citation decisions and measured usage appear here.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="border-b border-slate-200 px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium text-slate-500">Trace {selected.trace_id}</p>
                    <h2 className="mt-1 text-lg font-semibold text-slate-900">
                      {selected.question_redacted}
                    </h2>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase text-slate-700">
                    {selected.status}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Metric label="Estimated cost" value={formatCost(selected.cost_usd)} />
                  <Metric label="Tokens" value={(selected.input_tokens + selected.output_tokens).toLocaleString()} />
                  <Metric label="Latency" value={formatDuration(selected.latency_ms)} />
                  <Metric label="Model" value={selected.model_name ?? "Unknown"} />
                </div>
                <p className="mt-3 text-[11px] leading-5 text-slate-500">
                  Cost basis: {selected.cost_basis}. Embedding and verifier provider costs may not be included.
                </p>
              </div>

              <div className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-900">Execution timeline</h3>
                  <span className="text-xs text-slate-500">{selected.steps.length} steps</span>
                </div>
                <ol className="space-y-3">
                  {selected.steps.map((step) => (
                    <li key={step.id} className="rounded-xl border border-slate-200 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">
                            {step.step_index + 1}
                          </span>
                          <span className="text-sm font-semibold text-slate-900">
                            {labelForStep(step.step_type)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          {step.tool_name && <span>{step.tool_name}</span>}
                          <span>{formatDuration(step.latency_ms)}</span>
                          <span className="rounded bg-slate-100 px-2 py-0.5">{step.status}</span>
                        </div>
                      </div>
                      <p className="mt-3 text-xs leading-5 text-slate-600">
                        {summaryText(step.input_summary)}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        {summaryText(step.output_summary)}
                      </p>
                    </li>
                  ))}
                </ol>
                {selected.answer_redacted && (
                  <div className="mt-5 rounded-xl bg-slate-50 p-4">
                    <h3 className="text-sm font-semibold text-slate-900">Answer recorded</h3>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                      {selected.answer_redacted}
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-slate-50 p-3">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
