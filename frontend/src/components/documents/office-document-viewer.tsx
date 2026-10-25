"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Presentation,
  X,
} from "lucide-react";
import type {
  DocumentResponse,
  DocumentUnitResponse,
  DocumentUnitListResponse,
} from "@/types/document";

const PAGE_SIZE = 30;
const PREVIEW_CHARS = 20000;

type Props = {
  document: DocumentResponse;
  onClose: () => void;
};

function typeName(extension: string): string {
  switch (extension.toLowerCase()) {
    case ".docx": return "Word document";
    case ".xlsx": return "Excel workbook";
    case ".pptx": return "PowerPoint presentation";
    default: return "Document";
  }
}

export function isOfficeDocument(extension: string): boolean {
  return [".docx", ".xlsx", ".pptx"].includes(extension.toLowerCase());
}

export function OfficeDocumentViewer({ document, onClose }: Props) {
  const [units, setUnits] = useState<DocumentUnitResponse[]>([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(0);
  const [status, setStatus] = useState(document.status);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadUnits = useCallback(async (nextOffset: number, signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(document.id)}/units?offset=${nextOffset}`,
        { cache: "no-store", signal },
      );
      if (!response.ok) {
        throw new Error(
          response.status === 401 ? "Please sign in to view this document." :
          response.status === 404 ? "Document not found or access denied." :
          "Unable to load the document preview.",
        );
      }
      const result = (await response.json()) as DocumentUnitListResponse;
      if (!Array.isArray(result.items)) throw new Error("Invalid document data.");
      setUnits(result.items);
      setTotal(result.total);
      setStatus(result.document_status);
      setOffset(nextOffset);
      setSelected(0);
    } catch (cause) {
      if (signal?.aborted) return;
      setError(cause instanceof Error ? cause.message : "Preview unavailable.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [document.id]);

  useEffect(() => {
    const controller = new AbortController();
    // Schedule the initial load after commit rather than synchronously
    // invoking state setters from the effect body.
    const frame = window.requestAnimationFrame(() => {
      void loadUnits(0, controller.signal);
    });
    return () => {
      window.cancelAnimationFrame(frame);
      controller.abort();
    };
  }, [loadUnits]);

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [onClose]);

  const currentUnit = units[selected];
  const icon = document.file_extension === ".xlsx" ? <FileSpreadsheet size={18}/> :
    document.file_extension === ".pptx" ? <Presentation size={18}/> :
    <FileText size={18}/>;

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="office-preview-title"
      className="fixed inset-0 z-[250] flex flex-col bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <header className="flex min-h-16 shrink-0 items-center gap-3 border-b border-[var(--aq-border)] bg-[var(--aq-bg-deep)] px-4 sm:px-6">
        <span className="rounded-lg bg-[var(--aq-blue-soft)] p-2 text-[var(--aq-blue)]">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="office-preview-title" className="truncate text-sm font-semibold">
            {document.original_filename}
          </h2>
          <p className="text-xs text-[var(--aq-muted)]">
            {typeName(document.file_extension)} · Read-only extracted text
          </p>
        </div>
        <a
          href={`/api/documents/${encodeURIComponent(document.id)}/content`}
          download={document.original_filename}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 text-xs font-semibold"
          aria-label="Download original Office file"
        >
          <ArrowDownToLine size={15} /> <span className="hidden sm:inline">Download</span>
        </a>
        <button type="button" onClick={onClose} aria-label="Close document preview"
          className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--aq-border)]">
          <X size={19}/>
        </button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
        <aside aria-label="Document sheets and sections"
          className="aq-scrollbar max-h-40 shrink-0 overflow-y-auto border-b border-[var(--aq-border)] bg-[var(--aq-panel)] p-3 sm:max-h-none sm:w-64 sm:border-b-0 sm:border-r">
          <p className="mb-3 px-2 text-xs font-semibold text-[var(--aq-muted)]">
            {status === "ready" ? "Sections, sheets or slides" : "Document status"}
          </p>
          <div className="space-y-1">
            {units.map((unit, index) => (
              <button key={unit.id} type="button"
                aria-pressed={selected === index}
                onClick={() => setSelected(index)}
                className={[
                  "w-full truncate rounded-lg px-3 py-2 text-left text-xs transition",
                  selected === index
                    ? "bg-[var(--aq-blue-soft)] font-semibold text-[var(--aq-blue)]"
                    : "text-[var(--aq-muted)] hover:bg-[var(--aq-card)]",
                ].join(" ")}
                title={unit.source_label}
              >
                {unit.source_label}
              </button>
            ))}
          </div>
          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between gap-2 border-t border-[var(--aq-border)] pt-3">
              <button type="button" aria-label="Previous sections"
                disabled={offset === 0 || loading}
                onClick={() => void loadUnits(Math.max(0, offset - PAGE_SIZE))}
                className="rounded-lg border border-[var(--aq-border)] p-2 disabled:opacity-30">
                <ChevronLeft size={16}/>
              </button>
              <span className="text-[10px] text-[var(--aq-muted)]">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
              </span>
              <button type="button" aria-label="Next sections"
                disabled={offset + PAGE_SIZE >= total || loading}
                onClick={() => void loadUnits(offset + PAGE_SIZE)}
                className="rounded-lg border border-[var(--aq-border)] p-2 disabled:opacity-30">
                <ChevronRight size={16}/>
              </button>
            </div>
          )}
        </aside>

        <section aria-label="Extracted Office document content"
          className="aq-scrollbar min-h-0 min-w-0 flex-1 overflow-y-auto p-4 sm:p-8">
          <div className="mx-auto max-w-4xl">
            {loading ? (
              <div role="status" className="flex items-center gap-3 text-sm text-[var(--aq-muted)]">
                <LoaderCircle size={18} className="animate-spin"/> Reading document…
              </div>
            ) : error ? (
              <p role="alert" className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
                <AlertCircle size={16}/> {error}
              </p>
            ) : currentUnit ? (
              <>
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">{currentUnit.source_label}</h3>
                  <span className="text-xs text-[var(--aq-muted)]">
                    {currentUnit.unit_type.toUpperCase()} · {currentUnit.char_count.toLocaleString()} characters
                  </span>
                </div>
                {currentUnit.unit_metadata.truncated === true && (
                  <p className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-300">
                    Part of this spreadsheet exceeded extraction limits. Download the original for complete data.
                  </p>
                )}
                <pre className="whitespace-pre-wrap break-words rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4 font-mono text-xs leading-6 text-[var(--aq-text-soft)] sm:p-6">
                  {currentUnit.content.slice(0, PREVIEW_CHARS) ||
                    "No readable text was extracted from this section."}
                </pre>
                {currentUnit.content.length > PREVIEW_CHARS && (
                  <p className="mt-3 text-xs text-[var(--aq-muted)]">
                    Preview displays the first {PREVIEW_CHARS.toLocaleString()} characters. Download the original for full content.
                  </p>
                )}
              </>
            ) : (
              <p className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4 text-sm text-[var(--aq-muted)]">
                {status === "ready"
                  ? "This document contains no extractable text. Images and charts may require OCR."
                  : "Process this file in Documents before previewing its extracted content."}
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
