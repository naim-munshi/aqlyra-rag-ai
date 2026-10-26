"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, CheckCircle2, CircleAlert, Globe2, LoaderCircle,
  LockKeyhole, MousePointer2, ShieldCheck, Download, X,
} from "lucide-react";
import { MarkdownMessage } from "@/components/chat/markdown-message";

type Plan = {
  plan_token: string;
  expires_at: string;
  task: string;
  start_url: string;
  allowed_host: string;
  max_pages: number;
  capabilities: string[];
  restrictions: string[];
};
type Report = {
  task: string;
  answer: string;
  visited: { citation: string; title: string; url: string; excerpt: string }[];
  steps: string[];
  model_name: string;
  finished_at: string;
};

function exportBrowserReport(report: Report) {
  const markdown = [
    "# Aqlyra Browser Agent",
    "",
    "**Task:** " + report.task,
    "**Finished:** " + report.finished_at,
    "**Model:** " + report.model_name,
    "",
    "## Research report",
    "",
    report.answer,
    "",
    "## Navigation steps",
    ...report.steps.map((step, index) => (index + 1) + ". " + step),
    "",
    "## Verified visited pages",
    ...report.visited.map((source) =>
      source.citation + " [" + source.title + "](" + source.url + ")"
    ),
    "",
  ].join("\n");
  const url = URL.createObjectURL(new Blob([markdown], {
    type: "text/markdown;charset=utf-8",
  }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aqlyra-browser-agent-report.md";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function getError(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return "Request failed. Check the agent configuration.";
}

export function BrowserAgentWorkspace() {
  const [task, setTask] = useState("");
  const [startUrl, setStartUrl] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState<"plan" | "run" | null>(null);
  const [error, setError] = useState("");

  async function planRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy("plan");
    setError("");
    setPlan(null);
    setReport(null);
    try {
      const response = await fetch("/api/agent/browser/plan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task, start_url: startUrl.trim() }),
      });
      const data: unknown = await response.json();
      if (!response.ok) { setError(getError(data)); return; }
      const proposed = data as Plan;
      if (!proposed.plan_token || !proposed.allowed_host) {
        setError("Invalid approval plan returned."); return;
      }
      setPlan(proposed);
    } catch { setError("Unable to reach browser agent."); }
    finally { setBusy(null); }
  }

  async function approveRun() {
    if (!plan || busy) return;
    if (new Date(plan.expires_at).getTime() < Date.now()) {
      setError("Approval expired. Create a new plan.");
      setPlan(null);
      return;
    }
    setBusy("run");
    setError("");
    try {
      const response = await fetch("/api/agent/browser/execute", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_token: plan.plan_token, approved: true }),
      });
      const data: unknown = await response.json();
      if (!response.ok) { setError(getError(data)); return; }
      const result = data as Report;
      if (!result.answer || !Array.isArray(result.visited)) {
        setError("Browser agent returned an incomplete report."); return;
      }
      setReport(result);
      setPlan(null);
    } catch { setError("The browser run failed or connection was interrupted."); }
    finally { setBusy(null); }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--aq-bg)] px-4 py-6 text-[var(--aq-text)] sm:px-8">
      <div className="mx-auto max-w-[960px]">
        <div className="flex items-center justify-between gap-3">
          <Link href="/web" className="inline-flex items-center gap-2 rounded-lg px-2 py-2 text-xs text-[var(--aq-muted)] hover:bg-[var(--aq-card)]">
            <ArrowLeft size={16} /> Web Research
          </Link>
          <span className="inline-flex items-center gap-2 rounded-full border border-[var(--aq-border)] bg-[var(--aq-panel)] px-3 py-1.5 text-[11px]">
            <ShieldCheck size={14} className="text-[var(--aq-cyan)]" />
            Approval-gated
          </span>
        </div>
        <div className="mt-9 flex items-start gap-4">
          <div className="rounded-2xl bg-[var(--aq-blue-soft)] p-3 text-[var(--aq-blue)]">
            <MousePointer2 size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold sm:text-3xl">Browser Agent</h1>
            <p className="mt-2 max-w-[660px] text-sm leading-6 text-[var(--aq-muted)]">
              Give Aqlyra a public website and a research goal. Review the proposed
              boundaries, approve execution, and get a cited record of pages visited.
            </p>
          </div>
        </div>

        <form onSubmit={planRun} className="mt-8 space-y-4 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5 sm:p-7">
          <label className="block text-xs font-semibold" htmlFor="agent-task">What should Aqlyra investigate?</label>
          <textarea id="agent-task" required minLength={5} maxLength={500} rows={3}
            value={task} onChange={e => setTask(e.target.value)}
            placeholder="Read this documentation site, follow relevant pages, and summarize deployment options."
            className="mt-2 w-full resize-y rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-sm outline-none focus:border-[var(--aq-blue)]"/>
          <label className="block text-xs font-semibold" htmlFor="agent-url">Starting public HTTPS URL</label>
          <input id="agent-url" type="url" required value={startUrl}
            onChange={e => setStartUrl(e.target.value)}
            placeholder="https://docs.example.com/guide"
            className="mt-2 h-12 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 text-sm outline-none focus:border-[var(--aq-blue)]"/>
          <p className="text-xs leading-5 text-[var(--aq-muted)]">
            Admin-approved websites only. This experimental mode uses a fresh,
            read-only browser without sign-in cookies or access to your Mac.
          </p>
          <button type="submit" disabled={!!busy}
            className="inline-flex h-11 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 text-sm font-semibold text-white disabled:opacity-50">
            {busy === "plan" ? <LoaderCircle size={17} className="animate-spin"/> : <LockKeyhole size={17}/>}
            Review execution plan
          </button>
        </form>

        {plan && (
          <section aria-label="Review browser execution" className="mt-6 rounded-2xl border border-[var(--aq-blue)] bg-[var(--aq-panel)] p-5 sm:p-7">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Approve browser execution</h2>
              <button type="button" aria-label="Cancel browser plan"
                onClick={() => setPlan(null)} className="rounded-full p-2 hover:bg-[var(--aq-card)]">
                <X size={18}/>
              </button>
            </div>
            <p className="mt-3 text-xs text-[var(--aq-muted)]">
              Website: <strong>{plan.allowed_host}</strong> · Up to {plan.max_pages} pages ·
              Expires {new Date(plan.expires_at).toLocaleTimeString()}
            </p>
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-[var(--aq-cyan)]">Allowed</h3>
                {plan.capabilities.map(item => <p key={item} className="mt-1 text-xs leading-5">✓ {item}</p>)}
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-amber-400">Blocked</h3>
                {plan.restrictions.map(item => <p key={item} className="mt-1 text-xs leading-5">× {item}</p>)}
              </div>
            </div>
            <button type="button" onClick={() => { void approveRun(); }} disabled={!!busy}
              className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 text-sm font-semibold text-white disabled:opacity-50">
              {busy === "run" ? <LoaderCircle size={17} className="animate-spin"/> : <CheckCircle2 size={17}/>}
              {busy === "run" ? "Reading approved pages…" : "Approve and run"}
            </button>
          </section>
        )}

        {error && (
          <p role="alert" className="mt-6 flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
            <CircleAlert size={17} /> {error}
          </p>
        )}

        {report && (
          <section className="mt-7 space-y-4">
            <article className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5 sm:p-7">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <Globe2 size={19} className="text-[var(--aq-blue)]"/> Agent report
                </h2>
                <button
                  type="button"
                  onClick={() => exportBrowserReport(report)}
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 text-xs font-semibold hover:bg-[var(--aq-card)]"
                >
                  <Download size={15}/> Export report
                </button>
              </div>
              <MarkdownMessage content={report.answer}/>
              <p className="mt-5 text-xs text-[var(--aq-muted)]">
                {report.model_name} · {new Date(report.finished_at).toLocaleString()}
              </p>
            </article>
            <article className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5 sm:p-7">
              <h2 className="mb-4 text-sm font-semibold">Audit trail</h2>
              {report.steps.map((step, i) => (
                <p key={i} className="mt-2 text-xs text-[var(--aq-muted)]">
                  {i + 1}. {step}
                </p>
              ))}
              <h3 className="mt-6 text-sm font-semibold">Visited sources</h3>
              {report.visited.map(src => (
                <a key={src.citation} href={src.url} target="_blank" rel="noopener noreferrer"
                  className="mt-2 block break-all text-sm text-[var(--aq-blue)] hover:underline">
                  {src.citation} {src.title}
                </a>
              ))}
            </article>
          </section>
        )}
      </div>
    </main>
  );
}
