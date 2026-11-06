"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
  ArrowLeft, BookOpen, CheckCircle2, ExternalLink, FileCheck2,
  FileUp, Globe2, GraduationCap, LoaderCircle, Plane, Search,
  Trash2, Sparkles, Clock3, MessageCircle, Send,
} from "lucide-react";
import type { DocumentListResponse, DocumentResponse } from "@/types/document";
import { uploadViaPrivateCloud } from "@/lib/api/cloud-upload";
import { MarkdownMessage } from "@/components/chat/markdown-message";
import { StudyFitWorkbench } from "@/components/study-abroad/program-fit-workbench";

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
type StudyAdvisor = {
  case_id: string;
  reviewed_checklist_count: number;
  not_applicable_count: number;
  total_checklist_count: number;
  linked_document_count: number;
  shortlisted_university_count: number;
  research_freshness: {
    topic: string; searched_at: string; age_days: number;
    stale: boolean; source_count: number;
    government_domain_sources: number;
    verification_status: string;
  }[];
  deadline_warnings: {
    university_id: string; university_name: string;
    user_entered_deadline: string; days_remaining: number;
    urgency: "past" | "soon"; verification_status: string;
  }[];
  next_actions: {
    id: string; title: string; reason: string;
    urgency: "urgent" | "next" | "later";
    research_topic: string | null;
    university_id: string | null;
  }[];
  generated_at: string;
  verification_status: string;
  disclaimer: string;
};
type ApiFailure = { detail?: unknown };

const RESEARCH_TOPICS = [
  { id: "universities", label: "University discovery" },
  { id: "admissions", label: "Admission requirements" },
  { id: "scholarships", label: "Scholarships & funding" },
  { id: "visa", label: "Student visa / permit" },
  { id: "embassy", label: "Embassy / consulate" },
  { id: "predeparture", label: "Pre-departure rules" },
  { id: "language", label: "Language requirements" },
  { id: "costs", label: "Tuition & living costs" },
  { id: "transfer", label: "Transfer / credit admissions" },
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


const CHAT_SETUP_STEPS = [
  { key: "nationality", question: "What is your citizenship / nationality?", hint: "Example: Bangladesh" },
  { key: "residence_country", question: "Which country do you currently live in?", hint: "Example: Japan" },
  { key: "destination_country", question: "Where do you want to study?", hint: "Example: Germany" },
  { key: "degree_level", question: "Which degree do you want to pursue?", hint: "Example: Master's" },
  { key: "study_field", question: "What subject do you want to study?", hint: "Example: AI / Computer Science" },
  { key: "intake", question: "When do you plan to start?", hint: "Example: Winter 2028" },
] as const;

function inferResearchTopic(text: string): typeof RESEARCH_TOPICS[number]["id"] {
  const q = text.toLowerCase();
  if (/scholarship|funding|financial aid|grant|奨学金|বৃত্তি|স্কলারশিপ/i.test(q)) return "scholarships";
  if (/visa|immigration|permit|residence status|ビザ|ভিসা/i.test(q)) return "visa";
  if (/embassy|consulate|appointment|大使館|দূতাবাস/i.test(q)) return "embassy";
  if (/transfer|credit|2nd year|3rd year|編入|単位|ট্রান্সফার/i.test(q)) return "transfer";
  if (/ielts|toefl|jlpt|language|german proficiency|日本語|英語|ভাষা/i.test(q)) return "language";
  if (/tuition|living cost|fees|budget|費用|学費|খরচ/i.test(q)) return "costs";
  if (/university|universities|college|program list|大学|বিশ্ববিদ্যালয়/i.test(q)) return "universities";
  if (/arrival|housing|before departure|travel insurance|出発|বাসা/i.test(q)) return "predeparture";
  return "admissions";
}

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
  const [casesLoaded, setCasesLoaded] = useState(false);
  const [active, setActive] = useState<StudyCase | null>(null);
  const [documents, setDocuments] = useState<LinkedDocument[]>([]);
  const [libraryDocs, setLibraryDocs] = useState<DocumentResponse[]>([]);
  const [librarySelection, setLibrarySelection] = useState("");
  const [universities, setUniversities] = useState<StudyUniversity[]>([]);
  const [universityForm, setUniversityForm] = useState({
    name: "", program: "", program_url: "", deadline: "",
  });
  const [reports, setReports] = useState<StudyReport[]>([]);
  const [advisor, setAdvisor] = useState<StudyAdvisor | null>(null);
  const [advisorError, setAdvisorError] = useState(false);
  const [advisorRevision, setAdvisorRevision] = useState(0);
  const [researchFocusId, setResearchFocusId] = useState("");
  const [specificQuestion, setSpecificQuestion] = useState("");
  const [customTopic, setCustomTopic] = useState("admissions");
  const refreshAdvisor = () => setAdvisorRevision(value => value + 1);
  const [creating, setCreating] = useState(false);
  const [activePanel, setActivePanel] = useState<"overview" | "universities" | "research" | "documents">("overview");
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatSource, setChatSource] = useState<"research" | "documents">("research");
  const [chatTopic, setChatTopic] = useState<"auto" | typeof RESEARCH_TOPICS[number]["id"]>("auto");
  const [lastDocumentChatQuestion, setLastDocumentChatQuestion] = useState("");
  const [setupStep, setSetupStep] = useState(0);
  const [setupReply, setSetupReply] = useState("");
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
      setCasesLoaded(true);
    }).catch(e => { if (!disposed) { setError(String(e)); setCasesLoaded(true); } });
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
      api<StudyAdvisor>("cases/" + id + "/advisor").catch(() => null),
    ]).then(([files, research, shortlist, guidance]) => {
      if (disposed) return;
      setDocuments(files);
      setReports(research);
      setUniversities(shortlist);
      setAdvisor(guidance);
      setAdvisorError(guidance === null);
    }).catch(e => { if (!disposed) setError(String(e)); });
    return () => { disposed = true; };
  }, [activeId, advisorRevision]); // Also refresh after saved case changes

  async function refreshLibraryDocs() {
    const response = await fetch("/api/documents", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to refresh My Documents");
    const data = (await response.json()) as DocumentListResponse;
    if (!Array.isArray(data.items)) throw new Error("Invalid document library response");
    setLibraryDocs(data.items);
  }

  // Reuse existing private documents instead of forcing a new upload.
  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    void fetch("/api/documents", { cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Unable to fetch My Documents");
        return await response.json() as DocumentListResponse;
      })
      .then(data => { if (!cancelled && Array.isArray(data.items)) setLibraryDocs(data.items); })
      .catch(() => { if (!cancelled) setLibraryDocs([]); });
    return () => { cancelled = true; };
  }, [activeId]);

  async function attachReadyDocument(documentId: string) {
    if (!active || !documentId) return;
    setBusy("attach"); setError(""); setNotice("");
    try {
      const attached = await api<LinkedDocument>(
        "cases/" + active.id + "/documents", "POST",
        { document_id: documentId, checklist_key: uploadKey },
      );
      setDocuments(previous => [
        ...previous.filter(file => file.document_id !== attached.document_id), attached,
      ]);
      replaceCase(await api<StudyCase>("cases/" + active.id));
      setLibrarySelection("");
      setNotice("Existing ready document linked privately; original remains in My Documents.");
      refreshAdvisor();
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function retrySavedDocument(documentId: string) {
    if (!documentId) return;
    setBusy("retry-index"); setError("");
    try {
      const response = await fetch(
        "/api/documents/" + encodeURIComponent(documentId) + "/retry-index",
        { method: "POST", cache: "no-store" },
      );
      if (!response.ok) {
        const data = await response.json().catch(() => null) as ApiFailure | null;
        throw new Error(typeof data?.detail === "string"
          ? data.detail : "Indexing is unavailable. The original file remains saved.");
      }
      await refreshLibraryDocs();
      setNotice("Indexing retry requested. Refresh later to check readiness.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  function replaceCase(updated: StudyCase) {
    setCases(previous => previous.map(item => item.id === updated.id ? updated : item));
    setActive(updated);
  }

  async function saveStudyCase(values: typeof form): Promise<boolean> {
    setBusy("create"); setError(""); setNotice("");
    try {
      const created = await api<StudyCase>("cases", "POST", {
        workflow: "student", ...values,
      });
      setCases(previous => [created, ...previous]);
      setActive(created);
      setDocuments([]); setReports([]); setUniversities([]);
      setAdvisor(null); setAdvisorError(false); setResearchFocusId(""); setSpecificQuestion("");
      setLastDocumentChatQuestion(""); setChatQuestion("");
      setCreating(false); setSetupStep(0); setSetupReply("");
      setNotice("Private study plan created. Ask Aqlyra a study question below.");
      return true;
    } catch (e) { setError(String(e)); return false; }
    finally { setBusy(""); }
  }

  async function createCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveStudyCase(form);
  }

  async function submitSetupReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy !== "") return;
    const answer = setupReply.trim();
    const step = CHAT_SETUP_STEPS[setupStep];
    if (!step || answer.length < 2 || answer.length > (step.key === "study_field" ? 120 : 80)) return;
    const updated = { ...form, [step.key]: answer };
    setForm(updated);
    if (setupStep === CHAT_SETUP_STEPS.length - 1) {
      await saveStudyCase(updated);
      return;
    }
    setSetupStep(value => value + 1);
    setSetupReply("");
  }

  async function updateStage(value: string) {
    if (!active) return;
    setBusy("stage"); setError("");
    try {
      replaceCase(await api<StudyCase>("cases/" + active.id, "PATCH", { stage: value }));
      refreshAdvisor();
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
      refreshAdvisor();
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
      refreshAdvisor();
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
      refreshAdvisor();
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function deleteUniversity(item: StudyUniversity) {
    if (!active) return;
    setBusy("university"); setError("");
    try {
      await api<void>("cases/" + active.id + "/universities/" + item.id, "DELETE");
      setUniversities(previous => previous.filter(value => value.id !== item.id));
      if (researchFocusId === item.id) setResearchFocusId("");
      refreshAdvisor();
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function research(topic: string, focusUniversityId = "", question = ""): Promise<boolean> {
    if (!active || !researchConsent) return false;
    setBusy("research"); setError(""); setNotice("");
    try {
      const result = await api<StudyReport>(
        "cases/" + active.id + "/research", "POST", {
          topic, confirm_share_profile: researchConsent,
          ...(focusUniversityId ? { focus_university_id: focusUniversityId } : {}),
          ...(question.trim() ? { specific_question: question.trim() } : {}),
        },
      );
      setReports(previous => [result, ...previous]);
      setNotice("Research saved to this journey. Verify important details with official sources.");
      if (question.trim()) setSpecificQuestion("");
      refreshAdvisor();
      return true;
    } catch (e) { setError(String(e)); return false; }
    finally { setBusy(""); }
  }

  async function sendStudyChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || busy !== "") return;
    const question = chatQuestion.trim();
    if (chatSource === "research") {
      if (!researchConsent || question.length < 12 || question.length > 160) return;
      const topic = chatTopic === "auto" ? inferResearchTopic(question) : chatTopic;
      const success = await research(topic, researchFocusId, question);
      if (success) setChatQuestion("");
      return;
    }
    if (!documentConsent || documents.length === 0 || question.length < 5 || question.length > 1200) return;
    setBusy("ask-documents"); setError(""); setNotice(""); setDocumentAnswer(null);
    try {
      const result = await api<CaseRagAnswer>(
        "cases/" + active.id + "/ask-documents", "POST",
        { question, confirm_share_documents: documentConsent },
      );
      setDocumentAnswer(result);
      setLastDocumentChatQuestion(question);
      setChatQuestion("");
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

  async function analyzeLinkedAcademicRecords() {
    if (!active || !documentConsent || documents.length === 0) return;
    setBusy("analyze-records"); setError(""); setDocumentAnswer(null);
    try {
      const answer = await api<CaseRagAnswer>(
        "cases/" + active.id + "/ask-documents", "POST", {
          question: "Review ONLY my attached academic records for explicitly stated GPA and its scale, institution, degree, language test score, completed credits, dates and any missing evidence. Cite each fact to the attached document and its section. Mark anything unmentioned as unknown; do not invent equivalences, admission eligibility or immigration rules.",
          confirm_share_documents: documentConsent,
        },
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
      const cloudEnabled = process.env.NEXT_PUBLIC_CLOUD_UPLOAD_ENABLED === "true";
      // Always use the existing 50 MiB direct upload grant when configured.
      // Legacy multipart fallback may be limited to 3 MiB by the Vercel proxy.
      const maxBytes = cloudEnabled ? 50 * 1024 * 1024 : 3 * 1024 * 1024;
      if (!file.size || file.size > maxBytes) {
        throw new Error(cloudEnabled
          ? "Choose a supported file up to 50 MiB."
          : "Proxy uploads accept at most 3 MiB. Use My Documents for existing files.");
      }
      let saved: DocumentResponse;
      if (cloudEnabled) {
        saved = await uploadViaPrivateCloud(file);
      } else {
        const body = new FormData();
        body.append("file", file);
        const response = await fetch("/api/documents/upload", {
          method: "POST", body, cache: "no-store",
        });
        if (!response.ok) {
          const data = await response.json().catch(() => null) as ApiFailure | null;
          throw new Error(typeof data?.detail === "string"
            ? data.detail : "Unable to store private document");
        }
        saved = await response.json() as DocumentResponse;
      }
      if (!saved.id) throw new Error("Invalid document upload response");
      // A signed cloud upload may be queued/processing. Never claim it was
      // indexed or attach it before the backend marks the file ready.
      if (!cloudEnabled && saved.status === "uploaded" &&
          process.env.NEXT_PUBLIC_CLOUD_UPLOAD_PROXY_ENABLED !== "true") {
        const response = await fetch(
          "/api/documents/" + encodeURIComponent(saved.id) + "/process",
          { method: "POST", cache: "no-store" },
        );
        if (response.ok) saved = await response.json() as DocumentResponse;
        // A 409/503 means bytes are stored, but indexing is not yet available.
        // Preserve the original and offer a later retry through My Documents.
      }
      try {
        await refreshLibraryDocs();
      } catch {
        // Storage may have succeeded even when the library refresh is offline.
        setLibraryDocs(previous => [saved, ...previous.filter(doc => doc.id !== saved.id)]);
      }
      if (saved.status === "ready") {
        try {
          const attached = await api<LinkedDocument>(
            "cases/" + active.id + "/documents", "POST",
            { document_id: saved.id, checklist_key: uploadKey },
          );
          setDocuments(previous => [
            ...previous.filter(d => d.document_id !== attached.document_id), attached,
          ]);
          replaceCase(await api<StudyCase>("cases/" + active.id));
          setNotice("Processed document linked privately to your journey.");
          refreshAdvisor();
        } catch {
          // A case-link failure must not be reported as an upload failure.
          setLibrarySelection(saved.id);
          setNotice("File is safely stored and ready, but was not linked. Select it from My Documents to retry.");
        }
      } else {
        setLibrarySelection(saved.id);
        setNotice(
          "File saved securely in My Documents, but indexing is not complete (" +
          saved.status + "). Refresh its status below and attach it once ready.",
        );
      }
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
      refreshAdvisor();
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
      setAdvisor(null); setAdvisorError(false); setResearchFocusId(""); setSpecificQuestion("");
      setDocumentAnswer(null); setDocumentConsent(false); setResearchConsent(false);
      setChatQuestion(""); setLastDocumentChatQuestion(""); setActivePanel("overview");
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
        </div>
        <header className="mb-5 mt-5 flex items-start gap-3">
          <span className="rounded-2xl bg-[var(--aq-blue-soft)] p-3 text-[var(--aq-blue)]">
            <GraduationCap size={25}/>
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Study Abroad</h1>
            <p className="mt-1 text-sm text-[var(--aq-muted)]">
              Ask questions naturally, or use guided steps to plan your next move.
            </p>
          </div>
        </header>
        <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
          <aside className={cardStyle + " order-2 h-fit lg:order-1"}>
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
                    setAdvisor(null); setAdvisorError(false); setResearchFocusId(""); setSpecificQuestion("");
                    setChatQuestion(""); setLastDocumentChatQuestion(""); setActivePanel("overview");
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
          <div className="order-1 min-w-0 space-y-5 lg:order-2">

            <section className={cardStyle} aria-label="Ask Aqlyra study assistant">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="rounded-xl bg-[var(--aq-blue-soft)] p-2.5 text-[var(--aq-blue)]">
                    <MessageCircle size={20} aria-hidden="true"/>
                  </span>
                  <div>
                    <h2 className="text-lg font-semibold">Ask Aqlyra</h2>
                    <p className="text-xs text-[var(--aq-muted)]">
                      {active ? "Ask about your study journey in one place" : "Create your private study plan with a short conversation"}
                    </p>
                  </div>
                </div>
                {active && <span className="max-w-full truncate rounded-full border border-[var(--aq-border)] px-3 py-1 text-[11px] text-[var(--aq-muted)]">
                  {active.destination_country} · {active.study_field}
                </span>}
              </div>
              {!active ? (
                !casesLoaded ? (
                  <div className="mt-5 rounded-xl border border-[var(--aq-border)] p-5 text-xs text-[var(--aq-muted)]" role="status">
                    Loading your saved study plans…
                  </div>
                ) : creating ? (
                  <div className="mt-5 text-sm text-[var(--aq-muted)]">
                    Complete the guided setup form below, or{" "}
                    <button type="button" onClick={() => setCreating(false)}
                      className="text-[var(--aq-blue)] underline">
                      return to chat setup
                    </button>.
                  </div>
                ) : (
                <div className="mt-5">
                  <div className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4">
                    <p className="text-xs text-[var(--aq-muted)]">Aqlyra · Step {setupStep + 1} of {CHAT_SETUP_STEPS.length}</p>
                    <p className="mt-2 text-sm font-medium">{CHAT_SETUP_STEPS[setupStep]?.question}</p>
                    <p className="mt-1 text-xs text-[var(--aq-muted)]">
                      Answer one question at a time. A private plan is saved only after all steps.
                    </p>
                  </div>
                  {setupStep > 0 && (
                    <div className="mt-3 space-y-2">
                      {CHAT_SETUP_STEPS.slice(0, setupStep).map(step => (
                        <div key={step.key} className="rounded-xl border border-[var(--aq-border)] px-3 py-2 text-xs">
                          <span className="text-[var(--aq-muted)]">{step.question}</span>
                          <p className="mt-1 font-semibold">{form[step.key]}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={event => { void submitSetupReply(event); }}>
                    <label htmlFor="study-chat-setup" className="sr-only">{CHAT_SETUP_STEPS[setupStep]?.question}</label>
                    <input id="study-chat-setup" required minLength={2}
                      maxLength={CHAT_SETUP_STEPS[setupStep]?.key === "study_field" ? 120 : 80}
                      placeholder={CHAT_SETUP_STEPS[setupStep]?.hint}
                      className={fieldStyle + " flex-1"}
                      value={setupReply} onChange={event => setSetupReply(event.target.value)} />
                    <button type="submit" disabled={busy !== "" || setupReply.trim().length < 2}
                      className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--aq-blue)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                      {busy === "create" ? "Saving…" : setupStep === CHAT_SETUP_STEPS.length - 1 ? "Create plan" : "Next"}
                      <Send size={14} aria-hidden="true"/>
                    </button>
                  </form>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    {setupStep > 0 && <button type="button" onClick={() => {
                      setSetupStep(s => s - 1);
                      setSetupReply("");
                    }} className="text-xs text-[var(--aq-blue)] underline">Previous question</button>}
                    <button type="button" onClick={() => setCreating(true)}
                      className="text-xs text-[var(--aq-blue)] underline">
                      Prefer a form? Use guided setup
                    </button>
                  </div>
                </div>
              )) : (
                <div className="mt-5">
                  <div className="flex flex-wrap gap-2" role="group" aria-label="Answer source">
                    <button type="button" aria-pressed={chatSource === "research"} onClick={() => setChatSource("research")}
                      className={"rounded-lg border px-3 py-2 text-xs " + (chatSource === "research"
                        ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]"
                        : "border-[var(--aq-border)] text-[var(--aq-muted)]")}>
                      Web research
                    </button>
                    <button type="button" aria-pressed={chatSource === "documents"}
                      onClick={() => setChatSource("documents")}
                      className={"rounded-lg border px-3 py-2 text-xs " + (chatSource === "documents"
                        ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]"
                        : "border-[var(--aq-border)] text-[var(--aq-muted)]")}>
                      My documents {documents.length ? "(" + documents.length + ")" : ""}
                    </button>
                  </div>
                  <div className="mt-4 max-h-[440px] min-h-[170px] space-y-4 overflow-y-auto rounded-xl border border-[var(--aq-border)] bg-[var(--aq-bg)] p-3 sm:p-4" role="log" aria-label="Study research answers">
                    {(chatSource === "research" ? reports.length === 0 : !documentAnswer) && (
                      <div className="py-6 text-center">
                        <Sparkles size={24} aria-hidden="true" className="mx-auto mb-3 text-[var(--aq-blue)]"/>
                        <p className="text-sm font-medium">What would you like to know?</p>
                        <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-[var(--aq-muted)]">
                          {chatSource === "research"
                            ? "Ask about universities, fees, scholarships, admission or visa rules. Answers include verifiable sources and are saved to your plan."
                            : "Ask about an attached document. Answers cite the files linked to this journey."}
                        </p>
                      </div>
                    )}
                    {chatSource === "research" && reports.slice(0, 5).reverse().map(report => (
                      <article key={report.id} className="space-y-2">
                        <div className="ml-auto max-w-[95%] rounded-2xl rounded-br-md bg-[var(--aq-blue-soft)] px-3 py-2 text-xs text-[var(--aq-text)] sm:max-w-[85%]">
                          <span className="font-semibold">Study question</span>
                          <p className="mt-1 whitespace-pre-wrap break-words">{report.question}</p>
                        </div>
                        <div className="max-w-full rounded-2xl rounded-bl-md border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-sm leading-relaxed">
                          <MarkdownMessage content={report.answer}/>
                          {report.sources.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-2 border-t border-[var(--aq-border)] pt-3">
                              {report.sources.slice(0, 5).map(source => (
                                <a key={source.citation} href={source.url} target="_blank" rel="noopener noreferrer"
                                  className="max-w-full truncate rounded-md border border-[var(--aq-border)] px-2 py-1 text-[11px] text-[var(--aq-blue)] hover:underline"
                                  title={source.title}>
                                  {source.citation} · {sourceHost(source.url)}
                                </a>
                              ))}
                            </div>
                          )}
                          <p className="mt-2 text-[11px] text-[var(--aq-muted)]">Saved research · verify details with official sources</p>
                        </div>
                      </article>
                    ))}
                    {chatSource === "documents" && documentAnswer && (
                      <article className="space-y-2">
                        <div className="ml-auto max-w-[95%] rounded-2xl rounded-br-md bg-[var(--aq-blue-soft)] p-3 text-xs sm:max-w-[85%]">
                          {lastDocumentChatQuestion || documentAnswer.question}
                        </div>
                        <div className="rounded-2xl rounded-bl-md border border-[var(--aq-border)] bg-[var(--aq-card)] p-3 text-sm">
                          <MarkdownMessage content={documentAnswer.answer}/>
                          {documentAnswer.citations.map(source => (
                            <p key={source.source_id} className="mt-2 break-words text-[11px] text-[var(--aq-muted)]">
                              {source.source_id} · {source.filename} · {source.source_label}
                            </p>
                          ))}
                          {documentAnswer.is_refusal && (
                            <p className="mt-2 text-xs text-amber-400">Not enough evidence in the attached files.</p>
                          )}
                        </div>
                      </article>
                    )}
                    {busy === "research" || busy === "ask-documents" ? (
                      <p role="status" className="text-xs text-[var(--aq-muted)]">
                        <LoaderCircle size={14} className="mr-2 inline animate-spin"/> Aqlyra is checking sources…
                      </p>
                    ) : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {([
                      "Find universities in " + active.destination_country + " for " + active.study_field,
                      "What are the admission requirements for my degree?",
                      "Which scholarships could fit this study plan?",
                    ] as const).map(question => (
                      <button key={question} type="button" disabled={busy !== ""}
                        onClick={() => { setChatSource("research"); setChatQuestion(question.slice(0, 160)); }}
                        className="rounded-full border border-[var(--aq-border)] px-3 py-1.5 text-left text-[11px] text-[var(--aq-muted)] hover:border-[var(--aq-blue)]">
                        {question}
                      </button>
                    ))}
                  </div>
                  <form onSubmit={event => { void sendStudyChat(event); }} className="mt-4 space-y-3">
                    {chatSource === "research" ? (
                      <label className="flex items-start gap-2 text-xs leading-5 text-[var(--aq-muted)]">
                        <input type="checkbox" checked={researchConsent}
                          onChange={event => setResearchConsent(event.target.checked)} className="mt-1" />
                        I agree to share my plan&apos;s country, nationality, degree, subject and intake
                        with external web research/AI providers. No uploaded files or private notes are shared.
                      </label>
                    ) : (
                      <label className="flex items-start gap-2 text-xs leading-5 text-[var(--aq-muted)]">
                        <input type="checkbox" checked={documentConsent}
                          onChange={event => setDocumentConsent(event.target.checked)} className="mt-1" />
                        I agree to share excerpts from files linked to this journey with the configured AI provider.
                        Other journeys are not searched.
                      </label>
                    )}
                    {chatSource === "research" && (
                      <details className="text-xs text-[var(--aq-muted)]">
                        <summary className="cursor-pointer">Research options</summary>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <label>Topic
                            <select value={chatTopic} className={fieldStyle + " mt-1"}
                              onChange={event => setChatTopic(event.target.value as typeof chatTopic)}>
                              <option value="auto">Auto-select topic</option>
                              {RESEARCH_TOPICS.map(topic => (
                                <option key={topic.id} value={topic.id}>{topic.label}</option>
                              ))}
                            </select>
                          </label>
                          <label>Focus on a shortlisted program
                            <select value={researchFocusId} className={fieldStyle + " mt-1"}
                              onChange={event => setResearchFocusId(event.target.value)}>
                              <option value="">All universities</option>
                              {universities.map(u => (
                                <option key={u.id} value={u.id}>{u.name} · {u.program}</option>
                              ))}
                            </select>
                          </label>
                        </div>
                      </details>
                    )}
                    <label htmlFor="study-chat-question" className="sr-only">Your study question</label>
                    <textarea id="study-chat-question" rows={2}
                      minLength={chatSource === "research" ? 12 : 5}
                      maxLength={chatSource === "research" ? 160 : 1200}
                      value={chatQuestion} onChange={event => setChatQuestion(event.target.value)}
                      placeholder={chatSource === "research"
                        ? "Ask a question about studying abroad…"
                        : "Ask about a file attached to this journey…"}
                      className={fieldStyle + " resize-y"} />
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] text-[var(--aq-muted)]">
                        {chatSource === "research"
                          ? chatQuestion.length + "/160 · Avoid personal IDs, bank details and private links"
                          : documents.length === 0
                            ? "Attach a processed document under Documents first"
                            : "Private documents attached: " + documents.length}
                      </p>
                      <button type="submit"
                        disabled={busy !== "" || (chatSource === "research"
                          ? !researchConsent || chatQuestion.trim().length < 12 || chatQuestion.trim().length > 160
                          : !documentConsent || documents.length === 0 || chatQuestion.trim().length < 5 || chatQuestion.trim().length > 1200)}
                        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-[var(--aq-blue)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                        <Send size={15} aria-hidden="true"/>
                        {busy === "research" || busy === "ask-documents" ? "Checking…" : "Ask Aqlyra"}
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </section>

            {creating && (
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
                <nav className="flex gap-2 overflow-x-auto pb-1" aria-label="Study plan navigation">
                  {([
                    ["overview", "My plan"],
                    ["universities", "Universities"],
                    ["research", "Explore topics"],
                    ["documents", "Documents"],
                  ] as const).map(([key, label]) => (
                    <button type="button" key={key} aria-pressed={activePanel === key}
                      onClick={() => setActivePanel(key)}
                      className={"min-h-10 shrink-0 rounded-lg border px-4 py-2 text-xs font-semibold transition " +
                        (activePanel === key
                          ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)] text-[var(--aq-blue)]"
                          : "border-[var(--aq-border)] text-[var(--aq-muted)] hover:bg-[var(--aq-card)]")}>
                      {label}
                    </button>
                  ))}
                </nav>
                <section hidden={activePanel !== "overview"} className={cardStyle} aria-label="Personalized Study Advisor">
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <Sparkles size={18} className="text-[var(--aq-blue)]"/> Smart Study Advisor
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    Suggested next steps based on this plan. Dates and requirements need official verification; Aqlyra does not predict acceptance or visa approval.
                  </p>
                  {advisor ? (
                    <>
                      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                        {([
                          ["Self-reviewed", advisor.reviewed_checklist_count + "/" + advisor.total_checklist_count],
                          ["Shortlisted", String(advisor.shortlisted_university_count)],
                          ["Linked files", String(advisor.linked_document_count)],
                        ] as const).map(([label, value]) => (
                          <div key={label} className="rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-3">
                            <span className="block text-[11px] text-[var(--aq-muted)]">{label}</span>
                            <strong className="mt-1 block text-lg">{value}</strong>
                          </div>
                        ))}
                      </div>
                      {advisor.deadline_warnings.length > 0 && (
                        <div className="mt-4 space-y-2">
                          {advisor.deadline_warnings.map(warning => (
                            <div key={warning.university_id}
                              className="flex items-start gap-2 rounded-lg border border-amber-500/30 p-3 text-xs leading-5">
                              <Clock3 size={16} className="mt-0.5 shrink-0 text-amber-400"/>
                              <span>
                                <strong>{warning.university_name}</strong>: {warning.user_entered_deadline}
                                {" · "}{warning.days_remaining < 0 ? "Possibly past" : warning.days_remaining + " days away"}
                                <span className="block text-[var(--aq-muted)]">
                                  User-entered date — check current official admissions deadlines before acting.
                                </span>
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      <h3 className="mt-5 text-sm font-semibold">Recommended next steps</h3>
                      <ol className="mt-2 space-y-2">
                        {advisor.next_actions.map((action, index) => (
                          <li key={action.id} className="rounded-xl border border-[var(--aq-border)] p-3">
                            <div className="flex items-center gap-2 text-xs">
                              <strong>{index + 1}. {action.title}</strong>
                              {action.urgency === "urgent" && <span className="text-amber-400">Time-sensitive</span>}
                            </div>
                            <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">{action.reason}</p>
                            {action.research_topic && (
                              <button type="button"
                                disabled={busy !== "" || !researchConsent}
                                onClick={() => { if (action.research_topic) void research(
                                  action.research_topic, action.university_id ?? researchFocusId,
                                ); }}
                                title={!researchConsent ? "Enable research consent below first" : undefined}
                                className="mt-2 rounded-lg border border-[var(--aq-blue)]/50 px-3 py-2 text-[11px] text-[var(--aq-blue)] disabled:opacity-40">
                                Research with cited sources
                              </button>
                            )}
                          </li>
                        ))}
                      </ol>
                      {advisor.research_freshness.length > 0 && (
                        <div className="mt-4 text-[11px] text-[var(--aq-muted)]">
                          <strong className="block text-xs text-[var(--aq-text)]">Saved research freshness</strong>
                          {advisor.research_freshness.map(report => (
                            <p className="mt-1" key={report.topic}>
                              {RESEARCH_TOPICS.find(t => t.id === report.topic)?.label ?? report.topic}
                              {" · "}{report.age_days} days old
                              {report.stale ? " · Recheck required" : " · Recent snapshot"}
                              {" · "}Still needs official verification
                            </p>
                          ))}
                        </div>
                      )}
                      <p className="mt-3 text-[11px] leading-5 text-[var(--aq-muted)]">
                        {advisor.disclaimer}
                      </p>
                    </>
                  ) : <div role="status" className="mt-3 text-xs text-[var(--aq-muted)]">
                    {advisorError ? "Advisor temporarily unavailable. Your saved study data is still accessible." : "Loading private guidance…"}
                    {advisorError && <button type="button" className="ml-2 underline"
                      onClick={refreshAdvisor}>Retry guidance</button>}
                  </div>}
                </section>
                <section hidden={activePanel !== "overview"} className={cardStyle}>
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
                <section hidden={activePanel !== "universities"} className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold">
                    <GraduationCap size={18}/> My university shortlist
                  </h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    Save official program links, manually verify admission deadlines and track applications.
                    Search results do not automatically prove eligibility or acceptance.
                  </p>
                  <label className="mt-3 flex items-start gap-2 text-xs leading-5 text-[var(--aq-muted)]">
                    <input type="checkbox" className="mt-1" checked={researchConsent}
                      onChange={event => setResearchConsent(event.target.checked)}/>
                    Allow opt-in university-source research using this plan&apos;s nationality, residence, destination,
                    study subject, degree and intake. Uploaded files are never sent.
                  </label>
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
                {activePanel === "universities" && (
                  <StudyFitWorkbench
                    key={active.id}
                    caseId={active.id}
                    revision={advisorRevision}
                    researchAllowed={researchConsent}
                    onResearch={() => { void research("universities"); }}
                    onEvidenceUpdated={refreshAdvisor}
                    onUseCandidate={url => {
                      setUniversityForm({ name: "", program: "", program_url: url, deadline: "" });
                      setNotice("Research link placed in the university form. Check the exact degree and institution, then save.");
                    }}
                  />
                )}
                <section hidden={activePanel !== "research"} className={cardStyle}>
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
                    No uploaded document content is sent. If a focused program is selected,
                    its university and program names are also shared; private notes and files are not.
                  </label>
                  <label className="mt-4 block text-xs text-[var(--aq-muted)]">
                    Focus research on one shortlisted program (optional)
                    <select value={researchFocusId} onChange={event => setResearchFocusId(event.target.value)}
                      className={fieldStyle + " mt-1"}>
                      <option value="">General research for this study plan</option>
                      {universities.map(item => <option key={item.id} value={item.id}>
                        {item.name} · {item.program}
                      </option>)}
                    </select>
                  </label>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {RESEARCH_TOPICS.map(topic => (
                      <button type="button" key={topic.id} disabled={busy !== "" || !researchConsent}
                        onClick={() => { void research(topic.id, researchFocusId); }}
                        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[var(--aq-border)] px-3 py-2 text-left text-xs transition hover:bg-[var(--aq-card)] disabled:opacity-50">
                        {busy === "research" ? <LoaderCircle size={16} className="animate-spin"/> : <Globe2 size={16} className="text-[var(--aq-blue)]"/>}
                        {topic.label}
                      </button>
                    ))}
                  </div>

                  <form className="mt-5 space-y-3 rounded-xl border border-[var(--aq-border)] p-3"
                    onSubmit={event => { event.preventDefault(); void research(customTopic, researchFocusId, specificQuestion); }}>
                    <h3 className="text-sm font-semibold">Ask a specific study question</h3>
                    <p className="text-[11px] leading-5 text-[var(--aq-muted)]">
                      Ask about academic credit transfer, admission eligibility, fees or funding.
                      Source-based research requires your consent above. Do not enter passport
                      numbers, bank accounts, personal email addresses or private URLs.
                    </p>
                    <label className="block text-xs text-[var(--aq-muted)]">
                      Research category
                      <select value={customTopic} onChange={event => setCustomTopic(event.target.value)}
                        className={fieldStyle + " mt-1"}>
                        {RESEARCH_TOPICS.map(topic => <option key={topic.id} value={topic.id}>
                          {topic.label}
                        </option>)}
                      </select>
                    </label>
                    <label className="block text-xs text-[var(--aq-muted)]">
                      My question
                      <textarea required minLength={12} maxLength={160} rows={3}
                        value={specificQuestion}
                        onChange={event => setSpecificQuestion(event.target.value)}
                        placeholder="Can I transfer credits from a Japanese university into year three?"
                        className={fieldStyle + " mt-1 resize-y"}/>
                    </label>
                    <button type="submit" disabled={busy !== "" || !researchConsent || specificQuestion.trim().length < 12}
                      className="rounded-lg bg-[var(--aq-blue)] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">
                      {busy === "research" ? "Researching sources…" : "Research my question"}
                    </button>
                  </form>
                  {reports.length === 0 && <p className="mt-3 text-xs text-[var(--aq-muted)]">No research yet. Select a topic above to retrieve cited live evidence.</p>}
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
                <section hidden={activePanel !== "documents"} className={cardStyle}>
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
                    <button type="button"
                      disabled={busy !== "" || !documentConsent || documents.length === 0}
                      onClick={() => { void analyzeLinkedAcademicRecords(); }}
                      className="ml-2 rounded-lg border border-[var(--aq-blue)] px-4 py-2 text-xs text-[var(--aq-blue)] disabled:opacity-50">
                      {busy === "analyze-records" ? "Analyzing attached records…" : "Analyze my transcripts & identify missing evidence"}
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
                <section hidden={activePanel !== "documents"} className={cardStyle}>
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
                <section hidden={activePanel !== "documents"} className={cardStyle}>
                  <h2 className="flex items-center gap-2 text-base font-semibold"><FileUp size={18}/> Process private documents</h2>
                  <p className="mt-2 text-xs leading-5 text-[var(--aq-muted)]">
                    PDF, DOCX, XLSX, PPTX, TXT, CSV and images supported by Aqlyra.
                    Secure cloud upload (up to 50 MiB when enabled) → indexing → private linking. Files stay in your existing authenticated document storage.
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
                  {busy === "upload" && <p className="mt-2 text-xs text-[var(--aq-muted)]"><LoaderCircle size={14} className="mr-1 inline animate-spin"/> Saving and checking indexing…</p>}
                  <div className="mt-4 rounded-xl border border-[var(--aq-border)] p-3">
                    <h3 className="text-xs font-semibold">Attach from My Documents (no re-upload)</h3>
                    <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
                      Only files marked ready can be attached. Queued or uploaded files must finish indexing first.
                      The original file remains in My Documents if you unlink it from this journey.
                    </p>
                    <label className="mt-3 block text-xs text-[var(--aq-muted)]">
                      Existing private file
                      <select value={librarySelection} onChange={event => setLibrarySelection(event.target.value)}
                        className={fieldStyle + " mt-1"}>
                        <option value="">Choose a saved document</option>
                        {libraryDocs.map(doc => (
                          <option value={doc.id} key={doc.id}>
                            {doc.original_filename} ({doc.status})
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" disabled={busy !== "" ||
                          libraryDocs.find(doc => doc.id === librarySelection)?.status !== "ready"}
                        onClick={() => { void attachReadyDocument(librarySelection); }}
                        className="rounded-lg bg-[var(--aq-blue)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
                        Attach ready file
                      </button>
                      <button type="button" disabled={busy !== ""}
                        onClick={() => { void refreshLibraryDocs().catch(e => setError(String(e))); }}
                        className="rounded-lg border border-[var(--aq-border)] px-3 py-2 text-xs">
                        Refresh document status
                      </button>
                      {(libraryDocs.find(doc => doc.id === librarySelection)?.status === "uploaded" ||
                        libraryDocs.find(doc => doc.id === librarySelection)?.status === "failed") && (
                        <button type="button" disabled={busy !== ""}
                          onClick={() => { void retrySavedDocument(librarySelection); }}
                          className="rounded-lg border border-[var(--aq-border)] px-3 py-2 text-xs">
                          Retry indexing
                        </button>
                      )}
                    </div>
                  </div>

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
