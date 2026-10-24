"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ExternalLink,
  Globe2,
  LoaderCircle,
  Search,
} from "lucide-react";
import { MarkdownMessage } from "@/components/chat/markdown-message";

type WebSource = {
  citation: string;
  title: string;
  url: string;
  excerpt: string;
  published_date: string | null;
};
type ResearchResult = {
  question: string;
  answer: string;
  sources: WebSource[];
  provider_name: string;
  model_name: string;
  searched_at: string;
};
type ErrorResponse = { detail?: string };

export function WebResearchWorkspace() {
  const [question, setQuestion] = useState("");
  const [maxSources, setMaxSources] = useState(4);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || question.trim().length < 3) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/api/web/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.trim(),
          max_sources: maxSources,
        }),
      });
      const payload = (await response.json()) as ResearchResult & ErrorResponse;
      if (!response.ok) {
        setError(typeof payload.detail === "string"
          ? payload.detail : "Web research failed.");
        return;
      }
      if (!payload.answer || !Array.isArray(payload.sources)) {
        setError("Invalid web research response.");
        return;
      }
      setResult(payload);
    } catch {
      setError("Unable to connect to Aqlyra.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] px-5 py-8 text-[var(--aq-text)] sm:px-10">
      <div className="mx-auto max-w-[950px]">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-[var(--aq-muted)] hover:text-[var(--aq-blue)]">
          <ArrowLeft size={16} /> Back to workspace
        </Link>
        <div className="mt-8 flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
            <Globe2 size={24} />
          </span>
          <div>
            <h1 className="text-2xl font-bold">Web Research</h1>
            <p className="mt-1 text-xs text-[var(--aq-muted)]">
              Live public web search, page extraction and source-linked AI answers
            </p>
          </div>
        </div>
        <form onSubmit={submit} className="mt-8 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5">
          <label htmlFor="web-question" className="text-sm font-semibold">
            What would you like to research?
          </label>
          <textarea
            id="web-question"
            required
            minLength={3}
            maxLength={600}
            rows={3}
            className="mt-3 w-full resize-y rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4 text-sm outline-none focus:border-[var(--aq-blue)]"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Find current research, compare sources, or investigate recent developments..."
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs text-[var(--aq-muted)]">
              Sources
              <select
                aria-label="Maximum web sources"
                value={maxSources}
                onChange={(event) => setMaxSources(Number(event.target.value))}
                className="rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 py-2 text-[var(--aq-text)]"
              >
                <option value={3}>3</option>
                <option value={4}>4</option>
                <option value={5}>5</option>
              </select>
            </label>
            <button type="submit" disabled={loading || question.trim().length < 3}
              className="flex h-11 items-center justify-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 text-sm font-semibold text-white disabled:opacity-60">
              {loading ? <LoaderCircle size={16} className="animate-spin" /> : <Search size={16} />}
              {loading ? "Researching sources..." : "Research the web"}
            </button>
          </div>
          <p className="mt-3 text-xs leading-5 text-[var(--aq-muted)]">
            Public web research only. Do not enter confidential documents or secrets.
            External search and AI providers receive your question and source excerpts.
          </p>
        </form>
        {error && (
          <p role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
            {error}
          </p>
        )}
        {result && (
          <div className="mt-7 space-y-5">
            <section className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
                <Globe2 size={17} className="text-[var(--aq-blue)]" /> Research answer
              </div>
              <MarkdownMessage content={result.answer} />
              <p className="mt-5 text-xs text-[var(--aq-muted)]">
                Model: {result.provider_name} / {result.model_name} ·
                Retrieved: {new Date(result.searched_at).toLocaleString()}
              </p>
            </section>
            <section className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-6">
              <h2 className="text-sm font-semibold">Web sources ({result.sources.length})</h2>
              <div className="mt-4 space-y-3">
                {result.sources.map((source) => (
                  <div key={source.citation} className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-start gap-2 break-all text-sm font-semibold text-[var(--aq-blue)] hover:underline"
                    >
                      {source.citation} {source.title} <ExternalLink size={13} className="mt-1 shrink-0" />
                    </a>
                    {source.published_date && (
                      <p className="mt-1 text-xs text-[var(--aq-muted)]">Published: {source.published_date}</p>
                    )}
                    <details className="mt-2 text-xs leading-6 text-[var(--aq-muted)]">
                      <summary className="cursor-pointer">Read evidence excerpt</summary>
                      <p className="mt-2 whitespace-pre-wrap break-words">{source.excerpt}</p>
                    </details>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
