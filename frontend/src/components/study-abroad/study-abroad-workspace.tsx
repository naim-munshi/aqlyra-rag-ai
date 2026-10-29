"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
  ArrowLeft, BookOpen, CheckCircle2, ExternalLink, FileCheck2,
  FileUp, Globe2, GraduationCap, LoaderCircle, Plane, Search,
  ShieldAlert, Trash2,
} from "lucide-react";
import type { DocumentResponse } from "@/types/document";
import { MarkdownMessage } from "@/components/chat/markdown-message";

type ChecklistItem = {
  title: string;
  state: string;
  evidence_url: string | null;
  document_id: string | null;
};
type StudyCase = {
  id: string;
  workflow: string;
  nationality: string;
  residence_country: string;
  destination_country: string;
  degree_level: string;
  study_field: string;
  intake: string;
  stage: string;
  notes: string;
  checklist: Record<string, ChecklistItem>;
  updated_at: string;
};
type StudyReport = {
  id: string;
  topic: string;
  answer: string;
  question: string;
  searched_at: string;
  verification_status: string;
  sources: {
    citation: string; title: string; url: string;
    source_type?: "official_authority_domain" | "unverified_external_source";
    excerpt: string; published_date: string | null;
  }[];
};
type StudyUniversity = {
  id: string; name: string; program: string; program_url: string;
  application_status: string; deadline: string; notes: string;
};
type CaseRagAnswer = {
  question: string;
  answer: string;
  is_refusal: boolean;
  searched_document_count: number;
  citations: {
    source_id: string;
    document_id: string;
    filename: string;
    source_label: string;
    excerpt: string;
  }[];
  note: string;
};
type LinkedDocument = {
  document_id: string;
  filename: string;
  status: string;
  checklist_key: string;
};
type ApiFailure = { detail?: unknown };

const RESEARCH_TOPICS = [
  { id: "universities", label: "University discovery" },
  { id: "admissions", label: "Admission requirements" },
  { id: "scholarships", label: "Scholarships & funding" },
  { id: "visa", label: "Student visa / permit" },
  { id: "embassy", label: "Embassy / consulate" },
  { id: "predeparture", label: "Pre-departure rules" },
] as const;

const STAGES = [
  ["profile", "Profile"],
  ["university", "Universities"],
  ["admission", "Admissions"],
  ["documents", "Documents"],
  ["scholarship", "Funding"],
  ["visa", "Visa research"],
  ["embassy", "Embassy"],
  ["predeparture", "Arrival"],
] as const;

const CHECK_STATES = [
  ["needs_verification", "Verify requirement"],
  ["not_started", "Not started"],
  ["in_progress", "In progress"],
  ["uploaded", "Uploaded"],
  ["reviewed", "Manually reviewed"],
  ["not_applicable", "Not applicable"],
] as const;

async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch("/api/study-abroad/" + path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null) as ApiFailure | null;
    throw new Error(typeof data?.detail === "string"
      ? data.detail : "Request failed (" + response.status + ")");
  }
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

function dateLabel(input: string): string {
  const time = new Date(input);
  return Number.isNaN(time.getTime()) ? "Date unknown" : time.toLocaleDateString();
}

function sourceHost(url: string): string {
  try { return new URL(url).hostname; } catch { return "Source"; }
}

export function StudyAbroadWorkspace() {
  const [cases, setCases] = useState<StudyCase[]>([]);
  const [active, setActive] = useState<StudyCase | null>(null);
  const [documents, setDocuments] = useState<LinkedDocument[]>([]);
  const [universities, setUniversities] = useState<StudyUniversity[]>([]);
  const [universityForm, setUniversityForm] = useState({
    name: "", program: "", program_url: "", deadline: "",
  });
  const [reports, setReports] = useState<StudyReport[]>([]);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploadKey, setUploadKey] = useState("academic");
  const [researchConsent, setResearchConsent] = useState(false);
  const [documentConsent, setDocumentConsent] = useState(false);
  const [documentQuestion, setDocumentQuestion] = useState("");
  const [documentAnswer, setDocumentAnswer] = useState<CaseRagAnswer | null>(null);
  const [form, setForm] = useState({
    nationality: "", residence_country: "", destination_country: "",
    degree_level: "Bachelor's", study_field: "", intake: "2027",
  });

  useEffect(() => {
    let disposed = false;
    void api<StudyCase[]>("cases").then(items => {
      if (disposed) return;
      setCases(items);
      if (items.length) setActive(items[0]);
    }).catch(e => { if (!disposed) setError(String(e)); });
    return () => { disposed = true; };
  }, []);

  const activeId = active?.id;
  useEffect(() => {
    if (!activeId) return;
    let disposed = false;
    const id = encodeURIComponent(activeId);
    void Promise.all([
      api<LinkedDocument[]>("cases/" + id + "/documents"),
      api<StudyReport[]>("cases/" + id + "/research"),
      api<StudyUniversity[]>("cases/" + id + "/universities"),
    ]).then(([files, research, shortlist]) => {
      if (disposed) return;
      setDocuments(files);
      setReports(research);
      setUniversities(shortlist);
    }).catch(e => { if (!disposed) setError(String(e)); });
    return () => { disposed = true; };
  }, [activeId]); // Reload only when switching cases

  function replaceCase(updated: StudyCase) {
    setCases(previous => previous.map(item => item.id === updated.id ? updated : item));
    setActive(updated);
  }

  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("create"); setError(""); setNotice("");
    try {
      const created = await api<StudyCase>("cases", "POST", {
        workflow: "student", ...form,
      });
      setCases(previous => [created, ...previous]);
      setActive(created);
      setDocuments([]); setReports([]); setUniversities([]);
      setCreating(false);
      setNotice("Private student journey created.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function updateStage(value: string) {
    if (!active) return;
    setBusy("stage"); setError("");
    try {
      replaceCase(await api<StudyCase>("cases/" + active.id, "PATCH", { stage: value }));
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function updateCheck(key: string, state: string, evidenceUrl?: string | null) {
    if (!active) return;
    setBusy(key); setError("");
    try {
      replaceCase(await api<StudyCase>(
        "cases/" + active.id + "/checklist/" + key, "PATCH", {
          state, ...(evidenceUrl !== undefined ? { evidence_url: evidenceUrl } : {}),
        },
      ));
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function addUniversity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active) return;
    setBusy("university"); setError(""); setNotice("");
    try {
      const added = await api<StudyUniversity>(
        "cases/" + active.id + "/universities", "POST", universityForm,
      );
      setUniversities(previous => [added, ...previous]);
      setUniversityForm({ name: "", program: "", program_url: "", deadline: "" });
      setNotice("University shortlisted. Verify program details and deadlines directly.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function setUniversityStatus(item: StudyUniversity, application_status: string) {
    if (!active) return;
    setBusy("university"); setError("");
    try {
      const result = await api<StudyUniversity>(
        "cases/" + active.id + "/universities/" + item.id,
        "PATCH", { application_status },
      );
      setUniversities(previous => previous.map(value =>
        value.id === result.id ? result : value));
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function deleteUniversity(item: StudyUniversity) {
    if (!active) return;
    setBusy("university"); setError("");
    try {
      await api<void>("cases/" + active.id + "/universities/" + item.id, "DELETE");
      setUniversities(previous => previous.filter(value => value.id !== item.id));
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function research(topic: string) {
    if (!active) return;
    setBusy("research"); setError(""); setNotice("");
    try {
      const result = await api<StudyReport>(
        "cases/" + active.id + "/research", "POST", { topic, confirm_share_profile: researchConsent },
      );
      setReports(previous => [result, ...previous]);
      setNotice("Research saved. Check each source against the official authority.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function askDocuments(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !documentConsent || documents.length === 0) return;
    setBusy("ask-documents"); setError(""); setDocumentAnswer(null);
    try {
      const answer = await api<CaseRagAnswer>(
        "cases/" + active.id + "/ask-documents", "POST",
        { question: documentQuestion.trim(), confirm_share_documents: documentConsent },
      );
      setDocumentAnswer(answer);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function uploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!active || !file) return;
    setBusy("upload"); setError(""); setNotice("");
    try {
      const payload = new FormData();
      payload.append("file", file);
      const result = await fetch("/api/documents/upload", {
        method: "POST", body: payload,
      });
      const raw = await result.json() as DocumentResponse | {
        detail?: { document_id?: string; message?: string } | string;
      };
      let documentId = "";
      if (result.ok && "id" in raw) {
        documentId = raw.id;
      } else if ("detail" in raw && raw.detail &&
        typeof raw.detail === "object" && raw.detail.document_id) {
        documentId = raw.detail.document_id;
      } else {
        throw new Error("Upload failed. Use a supported file under 25 MiB.");
      }
      const process = await fetch(
        "/api/documents/" + encodeURIComponent(documentId) + "/process",
        { method: "POST" },
      );
      // Already-processed duplicates need not run again.
      if (!process.ok && process.status !== 409) {
        const detail = await process.json().catch(() => null) as ApiFailure | null;
        throw new Error(typeof detail?.detail === "string"
          ? detail.detail : "Document extraction failed.");
      }
      const attached = await api<LinkedDocument>(
        "cases/" + active.id + "/documents", "POST",
        { document_id: documentId, checklist_key: uploadKey },
      );
      setDocuments(previous => [
        ...previous.filter(d => d.document_id !== attached.document_id), attached,
      ]);
      replaceCase(await api<StudyCase>("cases/" + active.id));
      setNotice("Document processed and linked privately. Review its contents before submission.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function unlink(documentId: string) {
    if (!active) return;
    setBusy("unlink"); setError("");
    try {
      await api<void>("cases/" + active.id + "/documents/" + documentId, "DELETE");
      setDocuments(previous => previous.filter(d => d.document_id !== documentId));
      replaceCase(await api<StudyCase>("cases/" + active.id));
      setNotice("Link removed. Original document is still in My Documents.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function removeCase() {
    if (!active || !window.confirm("Delete this plan and its research snapshots? Uploaded documents will remain in My Documents.")) return;
    setBusy("delete"); setError("");
    try {
      await api<void>("cases/" + active.id, "DELETE");
      const remaining = cases.filter(item => item.id !== active.id);
      setCases(remaining);
      setActive(remaining[0] ?? null);
      setDocuments([]); setReports([]); setUniversities([]);
      setDocumentAnswer(null); setDocumentConsent(false); setResearchConsent(false);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  const fieldStyle = "min-w-0 w-full rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-3 py-2.5 text-sm text-[var(--aq-text)] outline-none focus:border-[var(--aq-blue)]";
  const cardStyle = "rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] p-4 sm:p-5";
  return (
    <main className="min-h-screen bg-[var(--aq-bg)] text-[var(--aq-text)]">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="inline-flex items-center gap-2 text-xs text-[var(--aq-muted)] hover:text-[var(--aq-blue)]">
            <ArrowLeft size={16}/> Back to Aqlyra
          </Link>
          <span className="rounded-full border border-[var(--aq-border)] px-3 py-1.5 text-[11px] text-[var(--aq-muted)]">
            Private planning • Not an embassy submission portal
          </span>
        </div>
        <header className="mt-6 mb-7 flex items-start gap-3">
          <span className="rounded-2xl bg-[var(--aq-blue-soft)] p-3 text-[var(--aq-blue)]">
            <GraduationCap size={26}/>
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Study Abroad</h1>
            <p className="mt-1 text-sm text-[var(--aq-muted)]">
              Your university-to-embassy research and document workspace
            </p>
          </div>
        </header>
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-[var(--aq-blue-soft)] px-3 py-2 text-xs font-semibold text-[var(--aq-blue)]">Student Visa · Available</span>
          <span aria-disabled="true" className="rounded-full border border-[var(--aq-border)] px-3 py-2 text-xs text-[var(--aq-muted)]">Job Visa · Planned</span>
        </div>
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-5 text-[var(--aq-muted)]">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-amber-400"/>
          <p>Requirements vary by citizenship, residence, university, degree and current law. All checklist items start unverified. Use official government, embassy and university sources before applying. Aqlyra does not guarantee admission, visa issuance, deadlines or appointments.</p>
        </div>
        <div className="grid gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
          <aside className={cardStyle + " h-fit"}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">My journeys</h2>
              <button type="button" onClick={() => setCreating(value => !value)}
                className="rounded-lg bg-[var(--aq-blue)] px-3 py-2 text-xs font-semibold text-white">
                + New
              </button>
            </div>
            {cases.length === 0 && <p className="text-xs leading-5 text-[var(--aq-muted)]">Create a journey to begin your plan.</p>}
            <div className="space-y-2">
              {cases.map(item => (
                <button key={item.id} type="button" disabled={busy !== ""} onClick={() => {
                    setActive(item); setResearchConsent(false); setDocumentConsent(false);
                    setDocumentAnswer(null); setDocuments([]); setReports([]); setUniversities([]);
                    setError(""); setNotice("");
                  }}
                  aria-pressed={active?.id === item.id}
                  className={"w-full rounded-xl border p-3 text-left transition " +
                    (active?.id === item.id
                      ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)]"
                      : "border-[var(--aq-border)] hover:bg-[var(--aq-card)]")}>
                  <span className="block truncate text-xs font-semibold">
                    {item.nationality} → {item.destination_country}
                  </span>
                  <span className="mt-1 block truncate text-[11px] text-[var(--aq-muted)]">
                    {item.study_field} · {item.intake}
                  </span>
                </button>
              ))}
            </div>
          </aside>
          <div className="min-w-0 space-y-5">
            {(creating || cases.length === 0) && (
              <form onSubmit={event => { void createCase(event); }} className={cardStyle}>
                <h2 className="mb-1 text-base font-semibold">Create student journey</h2>
                <p className="mb-4 text-xs text-[var(--aq-muted)]">No passport number, date of birth or bank statement is needed to make a plan.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {([
                    ["nationality", "Citizenship / nationality", "Bangladesh"],
                    ["residence_country", "Where you currently live", "Japan"],
                    ["destination_country", "Where you want to study", "Germany"],
                    ["degree_level", "Degree level", "Master's"],
                    ["study_field", "Subject / major", "Computer Science"],
                    ["intake", "Planned intake", "Winter 2027"],
                  ] as const).map(([key,label,placeholder]) => (
                    <label key={key} className="block text-xs text-[var(--aq-muted)]">
                      {label}
                      <input required maxLength={key === "study_field" ? 120 : 80}
                        className={fieldStyle + " mt-1"} placeholder={placeholder}
                        value={form[key]}
                        onChange={event => setForm(old => ({ ...old, [key]: event.target.value }))}/>
                    </label>
                  ))}
                </div>
                <div className="mt-4 flex gap-2">
                  <button type="submit" disabled={busy !== ""}
                    className="rounded-lg bg-[var(--aq-blue)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                    {busy === "create" ? "Creating…" : "Create plan"}
                  </button>
                  {cases.length > 0 && <button type="button" onClick={() => setCreating(false)}
                    className="rounded-lg border border-[var(--aq-border)] px-4 py-2 text-sm">Cancel</button>}
                </div>
              </form>
            )}
            {error && <p role="alert" className="rounded-lg border border-red-400/30 p-3 text-sm text-red-400">{error}</p>}
            {notice && <p role="status" className="rounded-lg border border-[var(--aq-border)] p-3 text-xs text-[var(--aq-muted)]">{notice}</p>}
            {active && (
              <>
                <section className={cardStyle}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h2 className="text-lg font-semibold">{active.study_field} · {active.degree_level}</h2>
                      <p className="mt-1 text-xs text-[var(--aq-muted)]">
                        {active.nationality} citizen • living in {active.residence_country} • to {active.destination_country} • {active.intake}
                      </p>
                    </div>
                    <button type="button" onClick={() => { void removeCase(); }} disabled={busy !== ""}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 px-3 py-2 text-xs text-red-400 disabled:opacity-50">
                      <Trash2 size={13}/> Delete plan
                    </button>
                  </div>
                  <label htmlFor="study-stage" className="mt-4 block text-xs text-[var(--aq-muted)]">My current stage</label>
                  <select id="study-stage" value={active.stage} disabled={busy !== ""}
                    className={fieldStyle + " mt-1"}
                    onChange={event => { void updateStage(event.target.value); }}>
                    {STAGES.map(([key,label]) => <option key={key} value={key}>{label}</option>)}
                  </select>
                </section>
                <section className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <GraduationCap size={18}/> My university shortlist
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    Save official program links, manually verify admission deadlines and track applications.
                    Search results do not automatically prove eligibility or acceptance.
                  </p>
                  <form onSubmit={event => { void addUniversity(event); }}
                    className="mt-4 grid gap-2 sm:grid-cols-2">
                    {([
                      ["name", "University", "Example University"],
                      ["program", "Program", "MSc Computer Science"],
                      ["program_url", "Program/admissions HTTPS URL", "https://university.example.edu/admissions"],
                      ["deadline", "Deadline (verify on site)", "2027-03-31"],
                    ] as const).map(([key,label,placeholder]) => (
                      <label key={key} className="text-xs text-[var(--aq-muted)]">{label}
                        <input required={key !== "deadline"} maxLength={key === "program_url" ? 2048 : 160}
                          placeholder={placeholder}
                          type={key === "program_url" ? "url" : "text"}
                          value={universityForm[key]}
                          onChange={event => setUniversityForm(old => ({
                            ...old, [key]: event.target.value,
                          }))}
                          className={fieldStyle + " mt-1"}/>
                      </label>
                    ))}
                    <button type="submit" disabled={busy !== ""}
                      className="rounded-lg bg-[var(--aq-blue)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2">
                      {busy === "university" ? "Saving…" : "Save university"}
                    </button>
                  </form>
                  <div className="mt-4 space-y-2">
                    {universities.map(item => (
                      <div key={item.id}
                        className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--aq-border)] p-3">
                        <a href={item.program_url} target="_blank" rel="noopener noreferrer"
                          className="min-w-0 flex-1 break-words text-xs hover:text-[var(--aq-blue)]">
                          <strong className="block">{item.name}</strong>
                          <span className="block text-[var(--aq-muted)]">
                            {item.program} {item.deadline ? "· Deadline to verify: " + item.deadline : ""}
                          </span>
                        </a>
                        <select value={item.application_status} disabled={busy !== ""}
                          aria-label={"Application status for " + item.name}
                          onChange={event => { void setUniversityStatus(item, event.target.value); }}
                          className="rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 py-2 text-[11px]">
                          {["researching", "shortlisted", "applied", "offer", "declined", "rejected"].map(value =>
                            <option value={value} key={value}>{value}</option>)}
                        </select>
                        <button type="button" aria-label={"Remove " + item.name}
                          disabled={busy !== ""}
                          onClick={() => { void deleteUniversity(item); }}
                          className="rounded-lg border border-[var(--aq-border)] p-2 disabled:opacity-50">
                          <Trash2 size={14}/>
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
                <section className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold"><Search size={18}/> Research universities, visas and embassies</h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    Uses opt-in live public Web Research. The search does not send your uploaded files.
                    Results are saved as dated evidence, not confirmed immigration or university decisions.
                  </p>
                  <label className="mt-3 flex items-start gap-2 text-xs leading-5 text-[var(--aq-muted)]">
                    <input type="checkbox" checked={researchConsent}
                      onChange={event => setResearchConsent(event.target.checked)}
                      className="mt-1"/>
                    I consent to share this plan&apos;s nationality, residence country, target country, degree,
                    study subject and intake with the configured external web research/AI providers.
                    No uploaded document content is sent.
                  </label>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {RESEARCH_TOPICS.map(topic => (
                      <button type="button" key={topic.id} disabled={busy !== "" || !researchConsent}
                        onClick={() => { void research(topic.id); }}
                        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 py-2 text-left text-xs transition hover:bg-[var(--aq-card)] disabled:opacity-50">
                        {busy === "research" ? <LoaderCircle size={16} className="animate-spin"/> : <Globe2 size={16} className="text-[var(--aq-blue)]"/>}
                        {topic.label}
                      </button>
                    ))}
                  </div>
                  {reports.length === 0 && <p className="mt-3 text-xs text-[var(--aq-muted)]">No research yet. Select one of the six topics.</p>}
                  <div className="mt-4 space-y-3">
                    {reports.map(report => (
                      <details key={report.id} className="rounded-xl border border-[var(--aq-border)] p-3">
                        <summary className="cursor-pointer text-xs font-semibold">
                          {RESEARCH_TOPICS.find(t => t.id === report.topic)?.label ?? report.topic} · {dateLabel(report.searched_at)}
                          <span className="ml-2 font-normal text-amber-400">Needs official verification</span>
                        </summary>
                        <div className="mt-3 text-sm leading-relaxed">
                          <MarkdownMessage content={report.answer}/>
                        </div>
                        <h3 className="mt-4 mb-2 text-xs font-semibold">Sources used</h3>
                        <div className="space-y-2">
                          {report.sources.map(source => (
                            <a key={source.citation} href={source.url} target="_blank" rel="noopener noreferrer"
                              className="flex items-start gap-2 rounded-lg border border-[var(--aq-border)] p-2 text-xs hover:border-[var(--aq-blue)]">
                              <ExternalLink size={14} className="mt-0.5 shrink-0"/>
                              <span className="min-w-0 break-words">
                                <strong>{source.citation} {source.title}</strong>
                                <span className="block text-[11px] text-[var(--aq-muted)]">
                                  {sourceHost(source.url)}
                                  {" · "}
                                  {source.source_type === "official_authority_domain"
                                    ? "Government-domain source; applicability still unverified"
                                    : "External source (unverified)"}
                                  {" · "}
                                  {source.published_date ? source.published_date : "Date not verified"}
                                </span>
                              </span>
                            </a>
                          ))}
                        </div>
                      </details>
                    ))}
                  </div>
                </section>
                <section className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <BookOpen size={18}/> Ask your case documents (private RAG)
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    Aqlyra retrieves evidence only from processed documents linked to this journey.
                    Answers include file/section references. An uploaded document does not prove
                    it is genuine or accepted by an embassy.
                  </p>
                  <form className="mt-4 space-y-3" onSubmit={event => { void askDocuments(event); }}>
                    <label className="block text-xs text-[var(--aq-muted)]">
                      Your question
                      <textarea required minLength={5} maxLength={1200} rows={2}
                        value={documentQuestion}
                        onChange={event => setDocumentQuestion(event.target.value)}
                        placeholder="What degree and graduation date appear in my uploaded academic records?"
                        className={fieldStyle + " mt-1 resize-y"}/>
                    </label>
                    <label className="flex items-start gap-2 text-xs leading-5 text-[var(--aq-muted)]">
                      <input type="checkbox" className="mt-1" checked={documentConsent}
                        onChange={event => setDocumentConsent(event.target.checked)}/>
                      I consent to sending retrieved excerpts from this journey&apos;s attached files
                      to Aqlyra&apos;s configured AI provider. No other journeys&apos; files are searched.
                    </label>
                    <button type="submit"
                      disabled={busy !== "" || !documentConsent || documents.length === 0 ||
                        documentQuestion.trim().length < 5}
                      className="rounded-lg bg-[var(--aq-blue)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">
                      {busy === "ask-documents" ? "Checking evidence…" : "Ask attached documents"}
                    </button>
                    {documents.length === 0 && <p className="text-xs text-[var(--aq-muted)]">
                      Attach and process a file below before asking a question.
                    </p>}
                  </form>
                  {documentAnswer && (
                    <div className="mt-4 space-y-3 rounded-xl border border-[var(--aq-border)] p-3">
                      <MarkdownMessage content={documentAnswer.answer}/>
                      {documentAnswer.is_refusal && (
                        <p className="text-xs text-amber-400">
                          Insufficient evidence in attached documents. Do not infer missing details.
                        </p>
                      )}
                      <p className="text-[11px] text-[var(--aq-muted)]">{documentAnswer.note}</p>
                      {documentAnswer.citations.length > 0 && (
                        <div className="space-y-2">
                          <h3 className="text-xs font-semibold">Document evidence</h3>
                          {documentAnswer.citations.map(source => (
                            <div key={source.source_id} className="rounded-lg bg-[var(--aq-card)] p-2 text-xs">
                              <strong>{source.source_id} · {source.filename} · {source.source_label}</strong>
                              <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
                                {source.excerpt}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </section>
                <section className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold"><FileCheck2 size={18}/> Document readiness</h2>
                  <p className="mt-2 text-xs text-[var(--aq-muted)]">
                    These are common planning prompts, not a government-approved checklist. Select each status manually after checking official requirements.
                  </p>
                  <div className="mt-4 space-y-2">
                    {Object.entries(active.checklist).map(([key,item]) => (
                      <div key={key} className="flex flex-col gap-2 rounded-lg border border-[var(--aq-border)] p-3 sm:flex-row sm:items-center">
                        <span className="flex min-w-0 flex-1 items-center gap-2 text-xs">
                          {item.state === "reviewed"
                            ? <CheckCircle2 size={16} className="shrink-0 text-green-400"/>
                            : <BookOpen size={16} className="shrink-0 text-[var(--aq-muted)]"/>}
                          <span>{item.title}</span>
                          {item.document_id && <FileCheck2 size={14} className="shrink-0 text-[var(--aq-blue)]"/>}
                        </span>
                        <div className="flex min-w-0 flex-col gap-1 sm:items-end">
                          {item.evidence_url && (
                            <a href={item.evidence_url} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] text-[var(--aq-blue)] hover:underline">
                              <ExternalLink size={12}/> Saved source
                            </a>
                          )}
                          <button type="button" disabled={busy !== ""}
                            onClick={() => {
                              const response = window.prompt(
                                "Public HTTPS source for this checklist item (confirm official status yourself)",
                                item.evidence_url ?? "",
                              );
                              if (response !== null) {
                                void updateCheck(key, item.state, response.trim() || null);
                              }
                            }}
                            className="text-left text-[11px] text-[var(--aq-muted)] underline decoration-dotted disabled:opacity-50">
                            {item.evidence_url ? "Edit source" : "Add source URL"}
                          </button>
                        </div>
                        <select value={item.state} disabled={busy !== ""}
                          aria-label={"Status for " + item.title}
                          onChange={event => { void updateCheck(key, event.target.value); }}
                          className="w-full rounded-lg border border-[var(--aq-border)] bg-[var(--aq-card)] px-2 py-2 text-[11px] sm:w-44">
                          {CHECK_STATES.map(([value,label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </div>
                    ))}
                  </div>
                </section>
                <section className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold"><FileUp size={18}/> Process private documents</h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    PDF, DOCX, XLSX, PPTX, TXT, CSV and images supported by Aqlyra.
                    Upload → extract/OCR → link to your checklist. Files stay in your existing authenticated document storage.
                    This does not check authenticity or guarantee embassy acceptance.
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <label className="text-xs text-[var(--aq-muted)]">
                      Document category
                      <select value={uploadKey} onChange={event => setUploadKey(event.target.value)}
                        className={fieldStyle + " mt-1"}>
                        {Object.entries(active.checklist).map(([key,item]) =>
                          <option key={key} value={key}>{item.title}</option>)}
                      </select>
                    </label>
                    <label className="text-xs text-[var(--aq-muted)]">
                      Select a file
                      <input type="file" disabled={busy !== ""}
                        accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp"
                        onChange={event => { void uploadFile(event); }}
                        className={fieldStyle + " mt-1 file:mr-3 file:rounded-md file:border-0 file:bg-[var(--aq-blue-soft)] file:px-2 file:py-1 file:text-[var(--aq-blue)]"}/>
                    </label>
                  </div>
                  {busy === "upload" && <p className="mt-2 text-xs text-[var(--aq-muted)]"><LoaderCircle size={14} className="mr-1 inline animate-spin"/> Processing file…</p>}
                  <div className="mt-3 space-y-2">
                    {documents.map(file => (
                      <div key={file.document_id} className="flex items-center justify-between gap-2 rounded-lg border border-[var(--aq-border)] p-2">
                        <span className="min-w-0 truncate text-xs" title={file.filename}>
                          {file.filename} <span className="text-[var(--aq-muted)]">({file.status})</span>
                        </span>
                        <button type="button" disabled={busy !== ""} aria-label={"Unlink " + file.filename}
                          onClick={() => { void unlink(file.document_id); }}
                          className="rounded-lg border border-[var(--aq-border)] px-2 py-1.5 text-[11px] disabled:opacity-50">
                          Unlink
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
                <footer className="pb-7 text-xs leading-5 text-[var(--aq-muted)]">
                  <Plane size={15} className="mr-2 inline"/> You remain responsible for verifying original university and government instructions and submitting applications yourself.
                </footer>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
