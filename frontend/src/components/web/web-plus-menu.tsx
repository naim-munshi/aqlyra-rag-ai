"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import {
  BookOpenText,
  ExternalLink,
  FileText,
  Globe2,
  Link2,
  ListChecks,
  Scale,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import type { ResearchMode } from "@/lib/web/research-request";

const TOOLS: {
  mode: ResearchMode;
  title: string;
  description: string;
  icon: typeof Search;
}[] = [
  {
    mode: "search", title: "Search the web",
    description: "Live public information with citations",
    icon: Globe2,
  },
  {
    mode: "deep", title: "Deep research",
    description: "Advanced search and detailed evidence",
    icon: Sparkles,
  },
  {
    mode: "compare", title: "Compare sources",
    description: "Find agreements and conflicting claims",
    icon: Scale,
  },
  {
    mode: "fact_check", title: "Fact-check",
    description: "Assess what the evidence really supports",
    icon: ListChecks,
  },
  {
    mode: "url", title: "Read a public URL",
    description: "Extract and analyze one HTTPS webpage",
    icon: Link2,
  },
];

type Props = {
  onClose: () => void;
  onSelect: (mode: ResearchMode) => void;
};

export function WebPlusMenu({ onClose, onSelect }: Props) {
  const firstItemRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    firstItemRef.current?.focus();

    function handleKeys(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const controls = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled])',
      );
      if (!controls?.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKeys);
    return () => window.removeEventListener("keydown", handleKeys);
  }, [onClose]);

  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex items-end justify-center px-0 sm:items-center sm:px-5">
      <button
        type="button"
        aria-label="Close research tools"
        className="pointer-events-auto absolute inset-0 bg-black/65 backdrop-blur-[3px]"
        onClick={onClose}
      />
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="research-tools-title"
        className="pointer-events-auto relative w-full max-w-[490px] rounded-t-[28px] border border-[var(--aq-border)] bg-[var(--aq-panel)] px-5 pb-[max(24px,env(safe-area-inset-bottom))] pt-4 shadow-2xl sm:rounded-[28px] sm:p-6"
      >
        <div className="mx-auto mb-4 h-1 w-12 rounded-full bg-[var(--aq-border)] sm:hidden" />
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 id="research-tools-title" className="text-lg font-semibold">Research tools</h2>
            <p className="mt-1 text-xs text-[var(--aq-muted)]">
              Choose how Aqlyra should use the web.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--aq-card)] text-[var(--aq-muted)] hover:text-[var(--aq-text)]"
          >
            <X size={18} />
          </button>
        </div>
        <div className="space-y-1.5">
          {TOOLS.map((tool, index) => {
            const Icon = tool.icon;
            return (
              <button
                key={tool.mode}
                ref={index === 0 ? firstItemRef : undefined}
                type="button"
                onClick={() => onSelect(tool.mode)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-[var(--aq-card)] focus-visible:outline-2 focus-visible:outline-[var(--aq-blue)]"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]">
                  <Icon size={19} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{tool.title}</span>
                  <span className="mt-0.5 block text-xs text-[var(--aq-muted)]">
                    {tool.description}
                  </span>
                </span>
              </button>
            );
          })}
          <Link
            href="/"
            className="flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-[var(--aq-card)]"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--aq-card)] text-[var(--aq-muted)]">
              <FileText size={19} />
            </span>
            <span className="flex-1">
              <span className="block text-sm font-semibold">Document workspace</span>
              <span className="mt-0.5 block text-xs text-[var(--aq-muted)]">
                Manage private files in the original Aqlyra workspace
              </span>
            </span>
            <ExternalLink size={15} className="text-[var(--aq-muted)]" />
          </Link>
        </div>
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-[var(--aq-card)] p-3 text-xs leading-5 text-[var(--aq-muted)]">
          <BookOpenText size={16} className="mt-0.5 shrink-0" />
          Web research uses external search and AI providers. Never paste passwords or private documents.
        </div>
      </section>
    </div>
  );
}
