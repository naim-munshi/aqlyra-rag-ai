"use client";

import {
  useCallback,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUp,
  Check,
  ChevronRight,
  Clipboard,
  Clock3,
  Download,
  ExternalLink,
  FileSearch,
  Globe2,
  Link2,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { MarkdownMessage } from "@/components/chat/markdown-message";
import { WebPlusMenu } from "@/components/web/web-plus-menu";
import type { ResearchMode } from "@/lib/web/research-request";

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

type ApiError = { detail?: string };

type RecentResult = {
  id: string;
  mode: ResearchMode;
  result: ResearchResult;
};

const MODE_LABELS: Record<ResearchMode, string> = {
  search: "Web search",
  deep: "Deep research",
  compare: "Compare sources",
  fact_check: "Fact-check",
  url: "Read a URL",
};

const SUGGESTIONS: {
  title: string;
  prompt: string;
  mode: ResearchMode;
  caption: string;
}[] = [
  {
    title: "Explore recent AI research",
    caption: "Find new developments with sources",
    prompt: "What are the latest verified developments in AI research this month?",
    mode: "search",
  },
  {
    title: "Compare two approaches",
    caption: "Find agreements, trade-offs and gaps",
    prompt: "Compare retrieval-augmented generation and long-context models using recent research.",
    mode: "compare",
  },
  {
    title: "Investigate a claim",
    caption: "Look for supporting and conflicting evidence",
    prompt: "Fact-check the claim that quantization always decreases LLM accuracy.",
    mode: "fact_check",
  },
  {
    title: "Build a research brief",
    caption: "Use advanced search and deeper extraction",
    prompt: "Research recent advances in efficient small language model inference.",
    mode: "deep",
  },
];

function sourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "Public source";
  }
}

function saveResearchMarkdown(result: ResearchResult) {
  const sources = result.sources.map((source) =>
    `- ${source.citation} [${source.title}](${source.url})${source.published_date ? ` — ${source.published_date}` : ""}`,
  );
  const markdown = [
    "# Aqlyra Web Research",
    "",
    `**Question:** ${result.question}`,
    `**Researched:** ${result.searched_at}`,
    "",
    result.answer,
    "",
    "## Sources",
    ...sources,
    "",
  ].join("\n");
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = "aqlyra-web-research.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export function WebResearchWorkspace() {
  const [question, setQuestion] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [mode, setMode] = useState<ResearchMode>("search");
  const [maxSources, setMaxSources] = useState(4);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [history, setHistory] = useState<RecentResult[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const composerRef = useRef<HTMLTextAreaElement>(null);
  const urlRef = useRef<HTMLInputElement>(null);
  const plusRef = useRef<HTMLButtonElement>(null);

  const active = history.find((entry) => entry.id === activeId) ?? null;
  const currentResult = active?.result ?? null;

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
    window.requestAnimationFrame(() => plusRef.current?.focus());
  }, []);

  function selectTool(nextMode: ResearchMode) {
    setMode(nextMode);
    setMenuOpen(false);
    setError("");
    window.requestAnimationFrame(() => {
      if (nextMode === "url") {
        urlRef.current?.focus();
      } else {
        composerRef.current?.focus();
      }
    });
  }

  function selectSuggestion(suggestion: (typeof SUGGESTIONS)[number]) {
    setMode(suggestion.mode);
    setQuestion(suggestion.prompt);
    setError("");
    composerRef.current?.focus();
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || question.trim().length < 3) return;
    if (mode === "url" && !sourceUrl.trim()) {
      setError("Add a public HTTPS URL before starting URL research.");
      urlRef.current?.focus();
      return;
    }

    setError("");
    setCopied(false);
    setLoading(true);

    try {
      const response = await fetch("/api/web/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.trim(),
          mode,
          max_sources: maxSources,
          ...(mode === "url" ? { source_url: sourceUrl.trim() } : {}),
        }),
      });
      const payload = (await response.json()) as ResearchResult & ApiError;

      if (!response.ok) {
        setError(
          typeof payload.detail === "string"
            ? payload.detail
            : "The research request could not be completed.",
        );
        return;
      }
      if (
        !payload ||
        typeof payload.answer !== "string" ||
        !payload.answer.trim() ||
        !Array.isArray(payload.sources) ||
        !payload.sources.length
      ) {
        setError("The research service returned incomplete evidence.");
        return;
      }

      const nextId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const record: RecentResult = { id: nextId, mode, result: payload };
      setHistory((previous) => [record, ...previous].slice(0, 6));
      setActiveId(nextId);
    } catch {
      setError("Unable to reach the Aqlyra web research service.");
    } finally {
      setLoading(false);
    }
  }

  async function copyAnswer() {
    if (!currentResult) return;
    try {
      await navigator.clipboard.writeText(currentResult.answer);
      setCopied(true);
    } catch {
      setError("Clipboard access is unavailable in this browser.");
    }
  }

  return (
    <main className="flex min-h-[100dvh] flex-col bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <header className="border-b border-[var(--aq-border)] bg-[var(--aq-bg-deep)]">
        <div className="mx-auto flex max-w-[1160px] items-center justify-between gap-3 px-4 py-4 sm:px-8">
          <Link
            href="/"
            aria-label="Return to Aqlyra workspace"
            className="inline-flex h-10 items-center gap-2 rounded-xl px-2 text-sm text-[var(--aq-muted)] hover:bg-[var(--aq-card)] hover:text-[var(--aq-text)]"
          >
            <ArrowLeft size={17} />
            <span className="hidden sm:inline">Workspace</span>
          </Link>
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
              <Globe2 size={20} />
            </span>
            <div>
              <p className="text-[14px] font-bold tracking-tight">Aqlyra Web</p>
              <p className="text-[10px] text-[var(--aq-muted)]">Research with real sources</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 py-1.5 text-[10px] font-semibold text-[var(--aq-text-soft)]">
            <ShieldCheck size={13} className="text-[var(--aq-cyan)]" />
            Cited answers
          </span>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1160px] flex-1 flex-col px-4 sm:px-8">
        {history.length > 0 && (
          <section aria-label="Recent research in this tab" className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--aq-muted)]">
                <Clock3 size={14} /> Recent in this tab
              </p>
              <button
                type="button"
                className="text-[11px] font-semibold text-[var(--aq-muted)] hover:text-[var(--aq-text)]"
                onClick={() => { setHistory([]); setActiveId(null); setError(""); }}
              >
                Clear
              </button>
            </div>
            <div className="aq-scrollbar flex gap-2 overflow-x-auto pb-1">
              {history.map((record) => (
                <button
                  key={record.id}
                  type="button"
                  onClick={() => { setActiveId(record.id); setError(""); setCopied(false); }}
                  className={[
                    "max-w-[245px] shrink-0 truncate rounded-full border px-4 py-2 text-xs",
                    record.id === activeId
                      ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] font-semibold"
                      : "border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-muted)]",
                  ].join(" ")}
                  title={record.result.question}
                >
                  {record.result.question}
                </button>
              ))}
            </div>
          </section>
        )}

        {!currentResult && !loading && (
          <section className="mx-auto flex w-full max-w-[770px] flex-1 flex-col justify-center py-9 sm:py-14">
            <span className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-[var(--aq-border)] bg-[var(--aq-panel)] px-3 py-2 text-xs text-[var(--aq-cyan)]">
              <Sparkles size={15} /> Research beyond your documents
            </span>
            <h1 className="max-w-[650px] text-[clamp(30px,5vw,54px)] font-bold leading-[1.12] tracking-tight">
              The web is vast.
              <span className="mt-1 block text-[var(--aq-blue)]">Find what matters.</span>
            </h1>
            <p className="mt-5 max-w-[530px] text-sm leading-7 text-[var(--aq-muted)] sm:text-base">
              Ask a question, check claims, or investigate a topic.
              Aqlyra searches public sources and builds a citation-backed answer.
            </p>
            <div className="mt-9 grid gap-3 sm:grid-cols-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion.title}
                  type="button"
                  onClick={() => selectSuggestion(suggestion)}
                  className="group flex min-h-28 flex-col justify-between rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4 text-left transition hover:border-[var(--aq-blue)] hover:bg-[var(--aq-card)]"
                >
                  <span className="flex items-center justify-between text-sm font-semibold">
                    {suggestion.title}
                    <ChevronRight size={16} className="text-[var(--aq-muted)] group-hover:text-[var(--aq-blue)]" />
                  </span>
                  <span className="mt-3 text-xs text-[var(--aq-muted)]">
                    {suggestion.caption}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {loading && (
          <section aria-live="polite" className="mx-auto flex w-full max-w-[760px] flex-1 flex-col items-center justify-center py-20 text-center">
            <span className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
              <LoaderCircle size={28} className="animate-spin" />
            </span>
            <h2 className="text-xl font-semibold">Researching the live web</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-[var(--aq-muted)]">
              Aqlyra is requesting public search results, extracting evidence
              and preparing a sourced response. The provider may take a moment.
            </p>
          </section>
        )}

        {currentResult && !loading && (
          <section className="grid flex-1 gap-6 py-7 lg:grid-cols-[minmax(0,1fr)_330px]">
            <article className="min-w-0 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5 sm:p-7">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2 rounded-full bg-[var(--aq-blue-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--aq-blue)]">
                  <FileSearch size={15} />
                  {active ? MODE_LABELS[active.mode] : "Web research"}
                </span>
                <span className="text-xs text-[var(--aq-muted)]">
                  {currentResult.sources.length} public sources
                </span>
              </div>
              <h2 className="mb-6 text-xl font-bold leading-8">
                {currentResult.question}
              </h2>
              <div className="border-t border-[var(--aq-border)] pt-6">
                <MarkdownMessage content={currentResult.answer} />
              </div>
              <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--aq-border)] pt-5">
                <span className="text-[11px] leading-5 text-[var(--aq-muted)]">
                  {currentResult.provider_name} · {currentResult.model_name}
                  {" · "}{new Date(currentResult.searched_at).toLocaleString()}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => { void copyAnswer(); }}
                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 text-xs font-semibold hover:bg-[var(--aq-card)]"
                  >
                    {copied ? <Check size={14} /> : <Clipboard size={14} />}
                    {copied ? "Copied" : "Copy"}
                  </button>
                  <button
                    type="button"
                    onClick={() => saveResearchMarkdown(currentResult)}
                    className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 text-xs font-semibold hover:bg-[var(--aq-card)]"
                  >
                    <Download size={14} /> Save
                  </button>
                </div>
              </div>
            </article>

            <aside className="min-w-0">
              <div className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4 sm:p-5 lg:sticky lg:top-5">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">
                    <Globe2 size={17} className="text-[var(--aq-blue)]" />
                    Evidence sources
                  </h3>
                  <span className="rounded-full bg-[var(--aq-card)] px-2 py-1 text-[10px] text-[var(--aq-muted)]">
                    {currentResult.sources.length}
                  </span>
                </div>
                <div className="space-y-3">
                  {currentResult.sources.map((source) => (
                    <div
                      key={source.citation}
                      className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3.5"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <span className="rounded-md bg-[var(--aq-blue-soft)] px-2 py-1 text-[11px] font-bold text-[var(--aq-blue)]">
                          {source.citation}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-xs text-[var(--aq-muted)]">
                          {sourceDomain(source.url)}
                        </span>
                      </div>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-start gap-1 text-sm font-semibold leading-5 text-[var(--aq-text)] hover:text-[var(--aq-blue)]"
                      >
                        <span className="min-w-0 flex-1 break-words">{source.title}</span>
                        <ExternalLink size={13} className="mt-1 shrink-0" />
                      </a>
                      {source.published_date && (
                        <p className="mt-2 text-[11px] text-[var(--aq-muted)]">
                          Published: {source.published_date}
                        </p>
                      )}
                      <details className="mt-3 border-t border-[var(--aq-border)] pt-3 text-xs text-[var(--aq-muted)]">
                        <summary className="cursor-pointer select-none font-medium">
                          View extracted evidence
                        </summary>
                        <p className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap break-words leading-6">
                          {source.excerpt}
                        </p>
                      </details>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
          </section>
        )}

        {error && (
          <div
            role="alert"
            className="mx-auto mt-5 w-full max-w-[860px] rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          >
            {error}
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error"
              className="ml-3 inline-flex align-middle"
            >
              <X size={15} />
            </button>
          </div>
        )}
      </div>

      <div className="sticky bottom-0 z-20 border-t border-[var(--aq-border)] bg-[var(--aq-bg-deep)] px-4 pb-[max(14px,env(safe-area-inset-bottom))] pt-3 sm:px-8 sm:pt-4">
        <form onSubmit={submit} className="mx-auto w-full max-w-[900px]">
          <div className="rounded-[22px] border border-[var(--aq-border)] bg-[var(--aq-panel)] px-3 py-3 shadow-xl sm:px-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--aq-blue-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--aq-blue)]">
                {mode === "url" ? <Link2 size={13} /> : <Search size={13} />}
                {MODE_LABELS[mode]}
              </span>
              {mode === "deep" && (
                <span className="text-[10px] text-[var(--aq-muted)]">
                  Advanced search may use more provider credits
                </span>
              )}
              {mode !== "url" && (
                <label className="flex items-center gap-2 text-[11px] text-[var(--aq-muted)]">
                  Sources
                  <select
                    aria-label="Maximum web sources"
                    value={maxSources}
                    onChange={(event) => setMaxSources(Number(event.target.value))}
                    className="rounded-md border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 py-1 text-[var(--aq-text)]"
                  >
                    <option value={3}>3</option>
                    <option value={4}>4</option>
                    <option value={5}>5</option>
                  </select>
                </label>
              )}
            </div>
            {mode === "url" && (
              <input
                ref={urlRef}
                aria-label="Public HTTPS URL"
                type="url"
                placeholder="https://example.com/article"
                inputMode="url"
                autoCapitalize="off"
                required
                maxLength={2048}
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                className="mb-2 h-11 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 text-sm outline-none focus:border-[var(--aq-blue)]"
              />
            )}
            <textarea
              ref={composerRef}
              aria-label="Ask Aqlyra Web Research"
              rows={2}
              maxLength={600}
              minLength={3}
              required
              value={question}
              onKeyDown={onComposerKeyDown}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={
                mode === "url"
                  ? "What should Aqlyra investigate in this webpage?"
                  : "Ask Aqlyra to research the live web..."
              }
              className="max-h-36 min-h-16 w-full resize-none bg-transparent px-1 py-1 text-sm leading-6 outline-none placeholder:text-[var(--aq-muted)]"
            />
            <div className="mt-2 flex items-center justify-between">
              <button
                ref={plusRef}
                type="button"
                onClick={() => setMenuOpen(true)}
                aria-label="Open research tools"
                aria-haspopup="dialog"
                aria-expanded={menuOpen}
                className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] transition hover:border-[var(--aq-blue)]"
              >
                <Plus size={21} />
              </button>
              <div className="flex items-center gap-3">
                <span className="hidden text-[11px] text-[var(--aq-muted)] sm:inline">
                  Enter to research · Shift+Enter for a new line
                </span>
                <button
                  type="submit"
                  disabled={loading || question.trim().length < 3 || (mode === "url" && !sourceUrl.trim())}
                  aria-label={loading ? "Research in progress" : "Start web research"}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--aq-blue)] text-white transition hover:bg-[var(--aq-blue-hover)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {loading ? <LoaderCircle size={19} className="animate-spin" /> : <ArrowUp size={20} />}
                </button>
              </div>
            </div>
          </div>
          <p className="mx-auto mt-2 max-w-[900px] text-center text-[10px] leading-4 text-[var(--aq-muted)]">
            Public web sources only. Your question and excerpts are shared with search and model providers.
          </p>
        </form>
      </div>

      {menuOpen && (
        <WebPlusMenu onClose={closeMenu} onSelect={selectTool} />
      )}
    </main>
  );
}
