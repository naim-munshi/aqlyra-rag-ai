"use client";

import {
  BookOpen,
  Check,
  Download,
  FilePlus2,
  LoaderCircle,
  RefreshCcw,
  ShieldCheck,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type ArtifactKind = "docx" | "xlsx" | "pptx" | "pdf" | "md";
type Artifact = {
  id: string;
  title: string;
  format: ArtifactKind;
  filename: string;
  size: number;
  created_at: string;
  provider_name: string;
  citation_count: number;
  source_document_ids: string[];
  content?: string;
};
type DocumentItem = { id: string; original_filename: string; status: string };
type ApiError = { detail?: string | { message?: string } };

const formats: { id: ArtifactKind; label: string; description: string }[] = [
  { id: "docx", label: "Word", description: ".docx" },
  { id: "xlsx", label: "Excel", description: ".xlsx" },
  { id: "pptx", label: "PowerPoint", description: ".pptx" },
  { id: "pdf", label: "PDF", description: ".pdf" },
  { id: "md", label: "Markdown", description: ".md" },
];

function errorText(body: ApiError | null, fallback: string): string {
  if (typeof body?.detail === "string") return body.detail;
  if (body?.detail && typeof body.detail === "object") {
    return body.detail.message ?? fallback;
  }
  return fallback;
}

export function ArtifactWorkspace() {
  const [title, setTitle] = useState("My Aqlyra Report");
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState<ArtifactKind>("docx");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [items, setItems] = useState<Artifact[]>([]);
  const [selected, setSelected] = useState<Artifact | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [filesResponse, docsResponse] = await Promise.all([
        fetch("/api/artifacts", { cache: "no-store" }),
        fetch("/api/documents", { cache: "no-store" }),
      ]);
      if (!filesResponse.ok) throw new Error("Unable to load your files");
      const files = (await filesResponse.json()) as { items?: Artifact[] };
      setItems(Array.isArray(files.items) ? files.items : []);
      if (docsResponse.ok) {
        const docs = (await docsResponse.json()) as { items?: DocumentItem[] };
        setDocuments((docs.items ?? []).filter((item) => item.status === "ready"));
      }
    } catch {
      setError("Unable to load your files. Check the backend connection.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function openArtifact(id: string) {
    setError("");
    try {
      const response = await fetch("/api/artifacts/" + encodeURIComponent(id), {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("File not found");
      const item = (await response.json()) as Artifact;
      setSelected(item);
      setDraft(item.content ?? "");
      setTitle(item.title);
      setFormat(item.format);
    } catch {
      setError("Unable to open this file.");
    }
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/artifacts/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          prompt: prompt.trim(),
          format,
          document_ids: sourceIds,
        }),
      });
      const data = (await response.json()) as Artifact & ApiError;
      if (!response.ok) throw new Error(errorText(data, "Unable to create file"));
      setSelected(data);
      setDraft(data.content ?? "");
      setNotice("Generated file saved privately. You can edit the source and save another version.");
      await refresh();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdited() {
    if (!draft.trim() || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/artifacts/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), content: draft, format }),
      });
      const data = (await response.json()) as Artifact & ApiError;
      if (!response.ok) throw new Error(errorText(data, "Unable to save edited file"));
      setSelected(data);
      setDraft(data.content ?? "");
      setNotice("New version saved. Your earlier file remains available.");
      await refresh();
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (busy || !window.confirm("Permanently delete this generated file?")) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/artifacts/" + encodeURIComponent(id), {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Unable to delete this file");
      if (selected?.id === id) {
        setSelected(null);
        setDraft("");
      }
      await refresh();
    } catch {
      setError("Unable to delete this file.");
    } finally {
      setBusy(false);
    }
  }

  function toggleSource(id: string) {
    setSourceIds((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : previous.length < 5 ? [...previous, id] : previous,
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-7 sm:px-8 lg:py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/" className="text-xs text-[var(--aq-blue)] hover:underline">
            Back to Aqlyra Chat
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">AI Files</h1>
          <p className="mt-1 text-sm text-[var(--aq-muted)]">
            Generate, edit and download real Office, PDF and Markdown files.
          </p>
        </div>
        <button type="button" onClick={() => void refresh()}
          className="flex items-center gap-2 rounded-xl border border-[var(--aq-border)] px-3 py-2 text-xs hover:bg-[var(--aq-card)]">
          <RefreshCcw size={14} /> Refresh
        </button>
      </div>

      {error && <div role="alert" className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
      {notice && <div role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-500/30 p-3 text-sm text-emerald-600"><Check size={16} />{notice}</div>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
        <div className="space-y-5">
          <form onSubmit={(event) => void generate(event)}
            className="space-y-5 rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <WandSparkles className="text-[var(--aq-blue)]" size={18} /> Create with AI
            </div>
            <label className="block text-xs font-medium">
              File title
              <input value={title} onChange={(event) => setTitle(event.target.value)}
                maxLength={120} required
                className="mt-2 w-full rounded-xl border border-[var(--aq-border)] bg-[var(--aq-bg)] p-3 text-sm outline-none focus:border-[var(--aq-blue)]" />
            </label>
            <label className="block text-xs font-medium">
              Describe what Aqlyra should create
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)}
                minLength={5} maxLength={4000} rows={5} required
                placeholder="Create a research report about AI Operating Systems with background, methodology, and key findings..."
                className="mt-2 w-full resize-y rounded-xl border border-[var(--aq-border)] bg-[var(--aq-bg)] p-3 text-sm leading-6 outline-none focus:border-[var(--aq-blue)]" />
            </label>
            <fieldset>
              <legend className="mb-2 text-xs font-medium">Output format</legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {formats.map((item) => (
                  <label key={item.id} className={[
                    "cursor-pointer rounded-xl border p-3 text-center transition",
                    format === item.id ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)]" : "border-[var(--aq-border)]",
                  ].join(" ")}>
                    <input className="sr-only" type="radio" name="format" value={item.id}
                      checked={format === item.id} onChange={() => setFormat(item.id)} />
                    <span className="block text-xs font-semibold">{item.label}</span>
                    <span className="mt-1 block text-[10px] text-[var(--aq-muted)]">{item.description}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            {documents.length > 0 && (
              <fieldset className="rounded-xl border border-[var(--aq-border)] p-3">
                <legend className="px-1 text-xs font-semibold">Ground with my documents (optional)</legend>
                <p className="mb-2 text-xs text-[var(--aq-muted)]">
                  Select up to 5 indexed documents. Aqlyra will use its existing citation-validated RAG answer.
                </p>
                <div className="max-h-36 space-y-2 overflow-y-auto">
                  {documents.map((document) => (
                    <label key={document.id} className="flex cursor-pointer items-center gap-2 text-xs">
                      <input type="checkbox" checked={sourceIds.includes(document.id)}
                        onChange={() => toggleSource(document.id)} />
                      <span className="truncate">{document.original_filename}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 text-xs text-[var(--aq-muted)]">
                <ShieldCheck size={14} /> Private by account
              </div>
              <button type="submit" disabled={busy || !prompt.trim() || !title.trim()}
                className="flex items-center gap-2 rounded-xl bg-[var(--aq-blue)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
                {busy ? <LoaderCircle size={16} className="animate-spin" /> : <FilePlus2 size={16} />}
                Generate file
              </button>
            </div>
          </form>

          {selected && (
            <section className="rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold">Edit source and save new version</h2>
                  <p className="mt-1 text-xs text-[var(--aq-muted)]">
                    Text preview, not a pixel-perfect Office preview.
                  </p>
                </div>
                <a href={"/api/artifacts/" + encodeURIComponent(selected.id) + "/download"}
                  className="flex items-center gap-2 rounded-xl border border-[var(--aq-border)] px-3 py-2 text-xs font-semibold">
                  <Download size={14} /> Download
                </a>
              </div>
              <textarea value={draft} onChange={(event) => setDraft(event.target.value)}
                maxLength={24000} rows={15}
                aria-label="Editable file source"
                className="mt-4 w-full resize-y rounded-xl border border-[var(--aq-border)] bg-[var(--aq-bg)] p-3 font-mono text-xs leading-6" />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-[var(--aq-muted)]">
                  {selected.provider_name} · {selected.citation_count} citations
                </span>
                <button type="button" disabled={busy || !draft.trim() || !title.trim()}
                  onClick={() => void saveEdited()}
                  className="rounded-xl bg-[var(--aq-blue)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">
                  Save edited copy
                </button>
              </div>
              {selected.citation_count > 0 && (
                <p className="mt-3 text-xs text-[var(--aq-muted)]">
                  Editing the source creates a new user-edited version without verified RAG citation status.
                </p>
              )}
            </section>
          )}
        </div>

        <section className="h-fit rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-5">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-[var(--aq-blue)]" />
            <h2 className="text-sm font-bold">My generated files</h2>
            <span className="ml-auto text-xs text-[var(--aq-muted)]">{items.length} / 50</span>
          </div>
          <p className="mt-2 text-xs text-[var(--aq-muted)]">
            Saved privately on the configured persistent upload volume.
          </p>
          <div className="mt-5 space-y-2">
            {loading && <p className="text-sm text-[var(--aq-muted)]">Loading files...</p>}
            {!loading && items.length === 0 && (
              <p className="rounded-xl border border-dashed border-[var(--aq-border)] p-6 text-center text-xs text-[var(--aq-muted)]">
                No files yet. Generate your first artifact or save an edited copy.
              </p>
            )}
            {items.map((item) => (
              <div key={item.id} className="rounded-xl border border-[var(--aq-border)] p-3">
                <button type="button" onClick={() => void openArtifact(item.id)}
                  className="w-full text-left text-sm font-semibold hover:text-[var(--aq-blue)]">
                  <span className="block truncate">{item.title}</span>
                  <span className="mt-1 block text-[11px] font-normal text-[var(--aq-muted)]">
                    {item.format.toUpperCase()} · {(item.size / 1024).toFixed(1)} KB · {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </button>
                <div className="mt-3 flex justify-end gap-2">
                  <a href={"/api/artifacts/" + encodeURIComponent(item.id) + "/download"}
                    aria-label={"Download " + item.title}
                    className="rounded-lg border border-[var(--aq-border)] p-2 hover:bg-[var(--aq-control)]">
                    <Download size={15} />
                  </a>
                  <button type="button" disabled={busy} onClick={() => void remove(item.id)}
                    aria-label={"Delete " + item.title}
                    className="rounded-lg border border-[var(--aq-border)] p-2 text-red-500 hover:bg-red-500/10 disabled:opacity-50">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-5 text-[11px] leading-5 text-[var(--aq-muted)]">
            Real AI generation needs a configured LLM. Document-grounded mode needs indexed evidence.
            Files are limited to 5 MiB each; PDF font coverage varies by language.
          </p>
        </section>
      </div>
    </div>
  );
}
